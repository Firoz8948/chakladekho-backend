from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin
from app.categories import service
from app.categories.schemas import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
    SubCategoryCreateRequest,
    SubCategoryUpdateRequest,
)
from app.database import get_db
from app.storage.bunny import upload_file

router = APIRouter()


@router.get("/")
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await service.get_all_categories(db, include_inactive=False)


@router.get("/admin/all")
async def admin_list_categories(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_all_categories(db, include_inactive=True)


@router.get("/admin/products-for-mapping")
async def products_for_mapping(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_all_products_for_mapping(db)


@router.get("/slug/{slug}")
async def get_category_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    cat = await service.get_category_by_slug(db, slug)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.get("/subcategories/slug/{slug}")
async def get_subcategory_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    sub = await service.get_subcategory_by_slug(db, slug)
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return sub


@router.get("/subcategories/{subcategory_id}")
async def get_subcategory(subcategory_id: int, db: AsyncSession = Depends(get_db)):
    sub = await service.get_subcategory_by_id(db, subcategory_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return sub


@router.get("/subcategories/{subcategory_id}/products")
async def get_subcategory_products(
    subcategory_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_subcategory_products(db, subcategory_id, page, limit)


@router.post("/{category_id}/subcategories", status_code=201)
async def create_subcategory(
    category_id: int,
    body: SubCategoryCreateRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    created = await service.create_subcategory(db, category_id, body.model_dump())
    if not created:
        raise HTTPException(status_code=404, detail="Category not found")
    return created


@router.put("/subcategories/{subcategory_id}")
async def update_subcategory(
    subcategory_id: int,
    body: SubCategoryUpdateRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await service.update_subcategory(
        db,
        subcategory_id,
        body.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return updated


@router.delete("/subcategories/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    deleted = await service.delete_subcategory(db, subcategory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return {"message": "Subcategory deleted"}


@router.post("/subcategories/{subcategory_id}/image")
async def upload_subcategory_image(
    subcategory_id: int,
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await service.get_subcategory_by_id(db, subcategory_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    image_url = await upload_file(file, "subcategories")
    return await service.set_subcategory_image(db, subcategory_id, image_url)


@router.get("/{category_id}/products")
async def get_category_products(
    category_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Categories hold subcategories only — products live on subcategories."""
    return await service.get_category_products(db, category_id, page, limit)


@router.get("/{category_id}")
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    cat = await service.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.post("/", status_code=201)
async def create_category(
    body: CategoryCreateRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_category(db, body.model_dump())


@router.put("/{category_id}")
async def update_category(
    category_id: int,
    body: CategoryUpdateRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await service.update_category(
        db,
        category_id,
        {k: v for k, v in body.model_dump().items() if v is not None},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        deleted = await service.delete_category(db, category_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}


@router.post("/{category_id}/image")
async def upload_category_image(
    category_id: int,
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    cat = await service.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    image_url = await upload_file(file, "categories")
    return await service.set_category_image(db, category_id, image_url)
