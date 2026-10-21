from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FreeGift


def _is_enabled(gift: FreeGift | None) -> bool:
    return bool(gift and gift.is_active and (gift.title or "").strip())


def serialize_admin(gift: FreeGift | None) -> dict:
    return {
        "title": (gift.title if gift else None) or "",
        "image_url": (gift.image_url if gift else None) or "",
        "is_active": bool(gift and gift.is_active),
        "enabled": _is_enabled(gift),
        "updated_at": gift.updated_at.isoformat() if gift and gift.updated_at else None,
    }


async def _get(db: AsyncSession, create: bool = False) -> FreeGift | None:
    result = await db.execute(select(FreeGift).order_by(FreeGift.id.asc()).limit(1))
    gift = result.scalar_one_or_none()
    if gift is None and create:
        gift = FreeGift(is_active=False)
        db.add(gift)
        await db.flush()
    return gift


async def get_public(db: AsyncSession) -> dict:
    gift = await _get(db)
    if not _is_enabled(gift):
        return {"enabled": False}
    return {
        "enabled": True,
        "title": gift.title.strip(),
        "image_url": gift.image_url or "",
    }


async def get_admin(db: AsyncSession) -> dict:
    return serialize_admin(await _get(db))


async def update(db: AsyncSession, data: dict) -> dict:
    gift = await _get(db, create=True)
    if "title" in data and data["title"] is not None:
        gift.title = data["title"].strip() or None
    if "is_active" in data and data["is_active"] is not None:
        gift.is_active = bool(data["is_active"])
    if gift.is_active and not (gift.title or "").strip():
        raise HTTPException(status_code=400, detail="Add a title before enabling the free gift")
    await db.commit()
    await db.refresh(gift)
    return serialize_admin(gift)


async def set_image(db: AsyncSession, image_url: str | None) -> dict:
    gift = await _get(db, create=True)
    gift.image_url = image_url
    await db.commit()
    await db.refresh(gift)
    return serialize_admin(gift)
