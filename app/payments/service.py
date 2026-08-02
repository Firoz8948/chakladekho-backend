import hashlib
import hmac
import json
import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select

from app.common import serialize_payment, utcnow
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Order, Payment
from app.orders import service as order_service
from app.orders.models import calc_subtotal, normalize_items, total_cart_weight_grams
from app.promocodes import service as promo_service

logger = logging.getLogger("payments")


def razorpay_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _client():
    if not razorpay_configured():
        raise HTTPException(
            status_code=503,
            detail="Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
        )
    import razorpay

    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def get_public_config() -> dict:
    return {
        "configured": razorpay_configured(),
        "key_id": settings.RAZORPAY_KEY_ID if razorpay_configured() else None,
        "currency": "INR",
    }


async def _build_checkout(
    customer: dict,
    address: dict,
    items: list[dict],
    promo_code: str | None = None,
    user_id: int | None = None,
) -> dict:
    normalized = normalize_items(items)
    subtotal = calc_subtotal(normalized)
    weight = total_cart_weight_grams(normalized)
    discount = 0.0
    applied_code = None

    async with AsyncSessionLocal() as db:
        from app.shipping_zones import service as zone_service

        shipping = await zone_service.resolve_shipping_charge(
            db,
            subtotal=subtotal,
            state=address.get("state"),
            pincode=address.get("pincode"),
            weight_grams=weight,
            payment_method="prepaid",
        )
        if promo_code:
            discount, shipping, applied_code = await promo_service.resolve_promo_for_order(
                db,
                promo_code,
                subtotal,
                shipping,
                user_id=user_id,
                phone=customer.get("phone") or customer.get("mobile"),
                consume=False,
            )

    return {
        "customer": customer,
        "address": address,
        "items": normalized,
        "subtotal": subtotal,
        "shipping_charge": shipping,
        "discount_amount": discount,
        "promo_code": applied_code,
        "total": round(max(subtotal - discount, 0) + shipping, 2),
    }


async def create_payment_order(
    customer: dict,
    address: dict,
    items: list[dict],
    user_id: int | None = None,
    promo_code: str | None = None,
    meta_event_id: str | None = None,
    meta_fbp: str | None = None,
    meta_fbc: str | None = None,
) -> dict:
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    checkout = await _build_checkout(
        customer, address, items, promo_code=promo_code, user_id=user_id
    )
    checkout["user_id"] = user_id
    if meta_event_id:
        checkout["meta_event_id"] = meta_event_id
    if meta_fbp:
        checkout["meta_fbp"] = meta_fbp
    if meta_fbc:
        checkout["meta_fbc"] = meta_fbc
    amount_paise = int(round(checkout["total"] * 100))
    if amount_paise < 100:
        raise HTTPException(
            status_code=400, detail="Order total must be at least ₹1.00"
        )

    receipt = f"rcpt_{uuid.uuid4().hex[:12]}"
    client = _client()

    try:
        rzp_order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "payment_capture": 1,
                "notes": {
                    "customer_name": (customer.get("name") or "")[:100],
                    "customer_phone": (customer.get("mobile") or "")[:20],
                    "user_id": str(user_id or ""),
                },
            }
        )
    except Exception as exc:
        logger.exception("Razorpay order.create failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Razorpay order creation failed: {exc}"
        ) from exc

    async with AsyncSessionLocal() as db:
        payment = Payment(
            amount=checkout["total"],
            currency="INR",
            razorpay_order_id=rzp_order["id"],
            status="created",
            checkout_snapshot=checkout,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        logger.info(
            "Razorpay order created %s amount=%s payment_row=%s",
            rzp_order["id"],
            checkout["total"],
            payment.id,
        )

    return {
        "razorpay_order_id": rzp_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "payment_id": str(payment.id),
    }


def _verify_signature(
    razorpay_order_id: str, razorpay_payment_id: str, signature: str
) -> bool:
    if not settings.RAZORPAY_KEY_SECRET:
        return False
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    generated = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(generated, signature or "")


def _fetch_razorpay_payment(razorpay_payment_id: str) -> dict:
    client = _client()
    try:
        return client.payment.fetch(razorpay_payment_id)
    except Exception as exc:
        logger.exception("Razorpay payment.fetch failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Could not fetch payment from Razorpay"
        ) from exc


def _assert_payment_amount(rzp_payment: dict, expected_rupees: float) -> None:
    paid_paise = int(rzp_payment.get("amount") or 0)
    expected_paise = int(round(float(expected_rupees) * 100))
    if paid_paise != expected_paise:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Payment amount mismatch: paid {paid_paise} paise, "
                f"expected {expected_paise} paise"
            ),
        )
    status = (rzp_payment.get("status") or "").lower()
    if status not in ("captured", "authorized"):
        raise HTTPException(
            status_code=400,
            detail=f"Payment not successful on Razorpay (status={status or 'unknown'})",
        )


async def _fulfill_paid_payment(
    payment: Payment,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    user_id: int | None,
    db,
) -> dict:
    """Create store order from snapshot if not already done. Idempotent."""
    if payment.order_db_id:
        order = await order_service.get_order(str(payment.order_db_id))
        return {
            "message": "Payment already verified",
            "order_id": order["order_id"],
            "order": order,
        }

    checkout = payment.checkout_snapshot
    if not checkout:
        raise HTTPException(status_code=400, detail="Checkout data missing")

    order = await order_service.create_order_from_checkout(
        checkout,
        razorpay_payment_id,
        razorpay_order_id,
        user_id=user_id or checkout.get("user_id"),
    )

    payment.order_db_id = int(order["id"])
    payment.razorpay_payment_id = razorpay_payment_id
    payment.status = "paid"
    payment.updated_at = utcnow()
    await db.commit()

    return {
        "message": "Payment verified and order saved",
        "order_id": order["order_id"],
        "order": order,
    }


async def verify_payment(payload: dict, user_id: int | None = None) -> dict:
    razorpay_order_id = payload["razorpay_order_id"]
    razorpay_payment_id = payload["razorpay_payment_id"]
    signature = payload["razorpay_signature"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Payment).where(Payment.razorpay_order_id == razorpay_order_id)
        )
        payment = result.scalar_one_or_none()

        if not _verify_signature(razorpay_order_id, razorpay_payment_id, signature):
            if payment:
                payment.status = "failed"
                payment.failure_reason = "signature_mismatch"
                payment.updated_at = utcnow()
                await db.commit()
            raise HTTPException(
                status_code=400, detail="Payment signature verification failed"
            )

        if not payment:
            raise HTTPException(status_code=404, detail="Payment session not found")

        if payment.status == "refunded":
            raise HTTPException(status_code=400, detail="Payment was refunded")

        # Merge Meta cookies/event id from verify payload into checkout snapshot
        snap = dict(payment.checkout_snapshot or {})
        if payload.get("meta_event_id"):
            snap["meta_event_id"] = payload["meta_event_id"]
        if payload.get("meta_fbp"):
            snap["meta_fbp"] = payload["meta_fbp"]
        if payload.get("meta_fbc"):
            snap["meta_fbc"] = payload["meta_fbc"]
        payment.checkout_snapshot = snap

        rzp_payment = _fetch_razorpay_payment(razorpay_payment_id)
        _assert_payment_amount(rzp_payment, payment.amount)

        return await _fulfill_paid_payment(
            payment,
            razorpay_payment_id,
            razorpay_order_id,
            user_id,
            db,
        )


async def handle_webhook(body: bytes, signature: str) -> dict:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.warning("Razorpay webhook received but RAZORPAY_WEBHOOK_SECRET is empty")
        # Still accept in development so dashboard tests don't hard-fail
        if settings.ENVIRONMENT.lower() not in ("development", "dev", "local"):
            raise HTTPException(
                status_code=503, detail="Webhook secret is not configured"
            )
    else:
        generated = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(generated, signature or ""):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8") if body else "{}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc

    event = payload.get("event") or ""
    entity = (
        (payload.get("payload") or {}).get("payment") or {}
    ).get("entity") or {}
    refund_entity = (
        (payload.get("payload") or {}).get("refund") or {}
    ).get("entity") or {}

    logger.info("Razorpay webhook event=%s", event)

    if event in ("payment.captured", "payment.authorized"):
        await _webhook_payment_success(entity)
    elif event in ("payment.failed",):
        await _webhook_payment_failed(entity)
    elif event in ("refund.processed", "refund.created"):
        await _webhook_refund(refund_entity or entity)
    else:
        logger.info("Unhandled Razorpay webhook event: %s", event)

    return {"status": "ok", "event": event}


async def _webhook_payment_success(entity: dict) -> None:
    razorpay_payment_id = entity.get("id")
    razorpay_order_id = entity.get("order_id")
    if not razorpay_order_id or not razorpay_payment_id:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Payment).where(Payment.razorpay_order_id == razorpay_order_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning(
                "Webhook payment for unknown order %s", razorpay_order_id
            )
            return
        if payment.order_db_id or payment.status == "paid":
            payment.razorpay_payment_id = (
                payment.razorpay_payment_id or razorpay_payment_id
            )
            payment.status = "paid"
            payment.updated_at = utcnow()
            await db.commit()
            return

        try:
            _assert_payment_amount(entity, payment.amount)
        except HTTPException as exc:
            payment.status = "failed"
            payment.failure_reason = str(exc.detail)
            payment.updated_at = utcnow()
            await db.commit()
            logger.error("Webhook amount/status check failed: %s", exc.detail)
            return

        await _fulfill_paid_payment(
            payment,
            razorpay_payment_id,
            razorpay_order_id,
            payment.checkout_snapshot.get("user_id")
            if payment.checkout_snapshot
            else None,
            db,
        )


async def _webhook_payment_failed(entity: dict) -> None:
    razorpay_order_id = entity.get("order_id")
    if not razorpay_order_id:
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Payment).where(Payment.razorpay_order_id == razorpay_order_id)
        )
        payment = result.scalar_one_or_none()
        if not payment or payment.status == "paid":
            return
        payment.status = "failed"
        payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
        payment.failure_reason = (
            entity.get("error_description")
            or entity.get("error_reason")
            or "payment_failed"
        )
        payment.updated_at = utcnow()
        await db.commit()


async def _webhook_refund(entity: dict) -> None:
    razorpay_payment_id = entity.get("payment_id") or entity.get("id")
    if not razorpay_payment_id:
        return
    # refund entity has payment_id; payment entity uses id
    pay_id = entity.get("payment_id") or None
    refund_id = entity.get("id") if entity.get("payment_id") else None

    async with AsyncSessionLocal() as db:
        q = select(Payment)
        if pay_id:
            q = q.where(Payment.razorpay_payment_id == pay_id)
        else:
            q = q.where(Payment.razorpay_payment_id == razorpay_payment_id)
        result = await db.execute(q)
        payment = result.scalar_one_or_none()
        if not payment:
            return
        payment.status = "refunded"
        if refund_id:
            payment.razorpay_refund_id = str(refund_id)
        payment.updated_at = utcnow()
        if payment.order_db_id:
            order_result = await db.execute(
                select(Order).where(Order.id == payment.order_db_id)
            )
            order = order_result.scalar_one_or_none()
            if order:
                order.payment_status = "refunded"
        await db.commit()


async def refund_payment(
    payment_id: str,
    amount: float | None = None,
    reason: str | None = None,
) -> dict:
    """Full or partial refund via Razorpay. Admin use."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Payment).where(Payment.id == int(payment_id))
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        if payment.status == "refunded":
            return serialize_payment(payment)
        if payment.status != "paid" or not payment.razorpay_payment_id:
            raise HTTPException(
                status_code=400, detail="Only paid Razorpay payments can be refunded"
            )

        refund_rupees = float(amount) if amount is not None else float(payment.amount)
        if refund_rupees <= 0 or refund_rupees > float(payment.amount) + 0.001:
            raise HTTPException(status_code=400, detail="Invalid refund amount")

        refund_paise = int(round(refund_rupees * 100))
        client = _client()
        try:
            body: dict = {"amount": refund_paise}
            if reason:
                body["notes"] = {"reason": reason[:200]}
            refund = client.payment.refund(payment.razorpay_payment_id, body)
        except Exception as exc:
            logger.exception("Razorpay refund failed: %s", exc)
            raise HTTPException(
                status_code=502, detail=f"Razorpay refund failed: {exc}"
            ) from exc

        payment.razorpay_refund_id = str(refund.get("id") or "")
        is_full = refund_paise >= int(round(float(payment.amount) * 100))
        payment.status = "refunded" if is_full else "partially_refunded"
        payment.updated_at = utcnow()

        if payment.order_db_id and is_full:
            order_result = await db.execute(
                select(Order).where(Order.id == payment.order_db_id)
            )
            order = order_result.scalar_one_or_none()
            if order:
                order.payment_status = "refunded"

        await db.commit()
        await db.refresh(payment)
        logger.info(
            "Refunded payment %s refund_id=%s amount=%s",
            payment.id,
            payment.razorpay_refund_id,
            refund_rupees,
        )
        return serialize_payment(payment)


async def get_payment(payment_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Payment).where(Payment.id == int(payment_id))
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return serialize_payment(payment)


async def list_payments_paginated(page: int = 1, limit: int = 20) -> dict:
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count(Payment.id)))).scalar() or 0
        result = await db.execute(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        payments = [serialize_payment(p) for p in result.scalars().all()]
        return {"payments": payments, "total": total, "page": page, "limit": limit}
