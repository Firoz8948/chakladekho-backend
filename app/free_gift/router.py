from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin
from app.database import get_db
from app.free_gift import service
from app.storage import upload_file

router = APIRouter()


class FreeGiftUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


@router.get("/")
async def public_free_gift(db: AsyncSession = Depends(get_db)):
    return await service.get_public(db)


@router.get("/admin")
async def admin_get_free_gift(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_admin(db)


@router.put("/admin")
async def admin_update_free_gift(
    body: FreeGiftUpdateRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update(db, body.model_dump())


@router.post("/admin/image")
async def admin_upload_free_gift_image(
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    url = await upload_file(file, "gifts")
    return await service.set_image(db, url)


@router.delete("/admin/image")
async def admin_remove_free_gift_image(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.set_image(db, None)
