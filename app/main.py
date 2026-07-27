from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.banners.router import router as banners_router
from app.categories.router import router as categories_router
from app.config import settings
from app.contact.router import router as contact_router
from app.database import connect_db, disconnect_db
from app.feeds.router import router as feeds_router
from app.meta.router import router as meta_router
from app.metafields.router import router as metafields_router
from app.orders.router import router as orders_router
from app.otp.router import router as otp_router
from app.payments.router import router as payments_router
from app.products.router import router as products_router
from app.promocodes.router import router as promocodes_router
from app.shipping.router import router as shipping_router
from app.shipping_zones.router import router as shipping_zones_router

prefix = settings.API_V1_PREFIX


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_path = Path("uploads")
uploads_path.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(products_router, prefix=f"{prefix}/products", tags=["Products"])
app.include_router(categories_router, prefix=f"{prefix}/categories", tags=["Categories"])
app.include_router(otp_router, prefix=prefix)
app.include_router(auth_router, prefix=prefix)
app.include_router(metafields_router, prefix=f"{prefix}/metafields", tags=["Metafields"])
app.include_router(orders_router, prefix=f"{prefix}/orders", tags=["Orders"])
app.include_router(payments_router, prefix=f"{prefix}/payments", tags=["Payments"])
app.include_router(shipping_router, prefix=f"{prefix}/shipping", tags=["Shipping"])
app.include_router(admin_router, prefix=f"{prefix}/admin", tags=["Admin"])
app.include_router(contact_router, prefix=f"{prefix}/contact", tags=["Contact"])
app.include_router(banners_router, prefix=f"{prefix}/banners", tags=["Banners"])
app.include_router(promocodes_router, prefix=f"{prefix}/promocodes", tags=["Promo Codes"])
app.include_router(
    shipping_zones_router, prefix=f"{prefix}/shipping-zones", tags=["Shipping Zones"]
)
app.include_router(feeds_router, prefix=f"{prefix}/feeds", tags=["Catalog Feeds"])
app.include_router(meta_router, prefix=f"{prefix}/meta", tags=["Meta"])


@app.get("/")
async def root():
    return {"message": "M Kharavad Company API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get(f"{prefix}/video-products")
async def public_video_products():
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models import VideoProduct
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(VideoProduct)
            .where(VideoProduct.is_active == True)  # noqa: E712
            .order_by(VideoProduct.position)
        )
        items = result.scalars().all()
        return [
            {
                "id": vp.id,
                "name": vp.name,
                "description": vp.description,
                "price": vp.price,
                "mrp": vp.mrp,
                "category": vp.category,
                "stock": vp.stock,
                "unit": vp.unit,
                "video_url": vp.video_url,
                "images": list(vp.images or []),
                "weight": vp.weight,
                "length_cm": vp.length_cm,
                "breadth_cm": vp.breadth_cm,
                "height_cm": vp.height_cm,
                "product_id": vp.product_id,
                "slug": f"video-{vp.id}",
            }
            for vp in items
        ]




def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8000")),
        reload=settings.ENVIRONMENT == "development",
    )


if __name__ == "__main__":
    main()
