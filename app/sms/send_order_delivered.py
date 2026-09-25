import logging
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger("sms")

RENFLAIR_DELIVERED_URL = "https://sms.renflair.in/V6.php"


def _renflair_ok(data: dict | None, raw: str) -> bool:
    if not data:
        return bool(raw and raw.strip())
    status = str(data.get("status") or "").upper()
    if status == "FAILED":
        return False
    if status == "SUCCESS":
        return True
    if data.get("return") is True:
        return True
    return False


async def send_order_delivered_sms(
    phone: str,
    customer_name: str,
    order_id: str,
) -> dict:
    """Send order-delivered SMS via Renflair V6 API (OID + CNAME)."""
    if not settings.RENFLAIR_API_KEY:
        logger.warning("RENFLAIR_API_KEY missing — skipping delivered SMS")
        return {"skipped": True}

    cname = (customer_name or "Customer").strip()[:50] or "Customer"
    oid = str(order_id)

    url = (
        f"{RENFLAIR_DELIVERED_URL}"
        f"?API={quote(settings.RENFLAIR_API_KEY, safe='')}"
        f"&PHONE={quote(str(phone), safe='')}"
        f"&OID={quote(oid, safe='')}"
        f"&CNAME={quote(cname, safe='')}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)

        raw = resp.text or ""
        if resp.status_code >= 400:
            logger.error(
                "Renflair delivered SMS failed: %s %s", resp.status_code, raw
            )
            return {"success": False, "status_code": resp.status_code, "raw": raw}

        try:
            data = resp.json() if raw.strip() else {}
        except Exception:
            data = {"raw": raw}

        ok = _renflair_ok(data if isinstance(data, dict) else None, raw)
        if not ok:
            logger.error("Renflair delivered SMS rejected: %s", data or raw)
            return {"success": False, "data": data, "raw": raw}

        logger.info(
            "Delivered SMS sent for %s to %s", oid, phone[-4:].rjust(10, "*")
        )
        return {"success": True, "data": data}
    except Exception as exc:
        logger.exception("Delivered SMS error: %s", exc)
        return {"success": False, "error": str(exc)}
