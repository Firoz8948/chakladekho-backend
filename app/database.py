import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def connect_db():
    from app.models import (  # noqa: F401
        Admin,
        BannerSlide,
        Cart,
        CartItem,
        Category,
        Contact,
        Order,
        OrderItem,
        OTP,
        Payment,
        Product,
        ProductImage,
        ProductSubcategory,
        ProductVariant,
        ProductVariantOption,
        PromoCode,
        MetafieldDefinition,
        Shipment,
        ShippingZone,
        SubCategory,
        User,
        VideoProduct,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import text

        await conn.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS "
                "category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_products_category_id ON products(category_id)"
            )
        )

        # Phone-based OTP migration (users + otps)
        await conn.execute(
            text("ALTER TABLE users ALTER COLUMN phone DROP NOT NULL")
        )
        await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_phone_key"))
        await conn.execute(
            text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
        )
        await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone_unique "
                "ON users(phone) WHERE phone IS NOT NULL AND phone <> ''"
            )
        )

        await conn.execute(text("DELETE FROM otps"))
        await conn.execute(
            text("ALTER TABLE otps ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
        )
        await conn.execute(text("ALTER TABLE otps DROP COLUMN IF EXISTS email"))
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_otps_phone ON otps(phone)")
        )

        await conn.execute(
            text(
                "ALTER TABLE product_variant_options "
                "ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE products "
                "ADD COLUMN IF NOT EXISTS metafields JSONB DEFAULT '{}'"
            )
        )
        await conn.execute(
            text("ALTER TABLE admins ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
        )
        await conn.execute(
            text(
                "ALTER TABLE admins ADD COLUMN IF NOT EXISTS company_name VARCHAR(255)"
            )
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(500)")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(500)")
        )
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS address_landmark VARCHAR(255)"
            )
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_city VARCHAR(100)")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_state VARCHAR(100)")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_pincode VARCHAR(10)")
        )
        await conn.execute(
            text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS address_landmark VARCHAR(255)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount DOUBLE PRECISION DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code VARCHAR(50)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE shipping_zones ADD COLUMN IF NOT EXISTS prepaid_rate DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE shipping_zones ADD COLUMN IF NOT EXISTS cod_rate DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "UPDATE shipping_zones SET prepaid_rate = rate "
                "WHERE prepaid_rate IS NULL"
            )
        )
        await conn.execute(
            text(
                "UPDATE shipping_zones SET cod_rate = COALESCE(prepaid_rate, rate) "
                "WHERE cod_rate IS NULL"
            )
        )

        # Razorpay payment extras
        await conn.execute(
            text(
                "ALTER TABLE payments "
                "ADD COLUMN IF NOT EXISTS razorpay_refund_id VARCHAR(255)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE payments "
                "ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(500)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE payments "
                "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
            )
        )

        # Subcategories + product.subcategory_id
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS subcategories (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(120) NOT NULL UNIQUE,
                    description TEXT,
                    image_url VARCHAR(500),
                    is_active BOOLEAN DEFAULT TRUE,
                    position INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_subcategories_category_id "
                "ON subcategories(category_id)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_subcategories_slug ON subcategories(slug)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE products "
                "ADD COLUMN IF NOT EXISTS subcategory_id INTEGER "
                "REFERENCES subcategories(id) ON DELETE SET NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS length_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS breadth_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS height_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE video_products ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE video_products ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE video_products ADD COLUMN IF NOT EXISTS length_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE video_products ADD COLUMN IF NOT EXISTS breadth_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE video_products ADD COLUMN IF NOT EXISTS height_cm DOUBLE PRECISION"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_products_subcategory_id "
                "ON products(subcategory_id)"
            )
        )

        # Many-to-many product ↔ subcategory
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS product_subcategories (
                    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    subcategory_id INTEGER NOT NULL REFERENCES subcategories(id) ON DELETE CASCADE,
                    PRIMARY KEY (product_id, subcategory_id)
                )
                """
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_product_subcategories_subcategory_id "
                "ON product_subcategories(subcategory_id)"
            )
        )
        # Backfill from legacy products.subcategory_id
        await conn.execute(
            text(
                """
                INSERT INTO product_subcategories (product_id, subcategory_id)
                SELECT id, subcategory_id FROM products
                WHERE subcategory_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """
            )
        )

        await conn.execute(
            text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_reels BOOLEAN DEFAULT FALSE"
            )
        )

    await seed_admin()
    await ensure_reels_category()
    await _migrate_products_to_subcategories()
    await _backfill_product_subcategories()
    print("PostgreSQL connected and tables ready")


async def disconnect_db():
    await engine.dispose()
    print("PostgreSQL disconnected")


async def _backfill_product_subcategories():
    """Ensure product_subcategories has a row for every products.subcategory_id."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO product_subcategories (product_id, subcategory_id)
                SELECT id, subcategory_id FROM products
                WHERE subcategory_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """
            )
        )


async def _migrate_products_to_subcategories():
    """Move products that only have category_id into a default subcategory."""
    import re

    from sqlalchemy import select

    from app.models import Category, Product, SubCategory

    def _slugify(name: str) -> str:
        s = name.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_-]+", "-", s)
        return s

    async with AsyncSessionLocal() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        for cat in cats:
            products = (
                await session.execute(
                    select(Product).where(
                        Product.category_id == cat.id,
                        Product.subcategory_id.is_(None),
                    )
                )
            ).scalars().all()
            if not products:
                continue

            default_slug = f"{cat.slug}-general"
            existing_sub = (
                await session.execute(
                    select(SubCategory).where(SubCategory.slug == default_slug)
                )
            ).scalar_one_or_none()
            if not existing_sub:
                existing_sub = SubCategory(
                    category_id=cat.id,
                    name="General",
                    slug=default_slug,
                    description=f"Default subcategory for {cat.name}",
                    is_active=True,
                    position=0,
                )
                session.add(existing_sub)
                await session.flush()

            for p in products:
                p.subcategory_id = existing_sub.id
                p.category = f"{cat.name} / {existing_sub.name}"

        await session.commit()


async def seed_admin():
    from sqlalchemy import select

    from app.models import Admin

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Admin).where(Admin.email == settings.ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()
        hashed = bcrypt.hashpw(
            settings.ADMIN_PASSWORD.encode(), bcrypt.gensalt()
        ).decode()
        if not existing:
            session.add(
                Admin(
                    email=settings.ADMIN_EMAIL,
                    password=hashed,
                    name=settings.ADMIN_USERNAME,
                    role="admin",
                    is_active=True,
                )
            )
            print(f"Admin seeded: {settings.ADMIN_USERNAME}")
        else:
            existing.password = hashed
            existing.name = settings.ADMIN_USERNAME
            print(f"Admin password synced: {settings.ADMIN_USERNAME}")
        await session.commit()


async def ensure_reels_category():
    """Ensure the special Reels category exists for admin + storefront."""
    from sqlalchemy import select

    from app.models import Category

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(
                select(Category).where(
                    (Category.is_reels == True) | (Category.slug == "reels")  # noqa: E712
                )
            )
        ).scalar_one_or_none()

        if existing:
            if not existing.is_reels:
                existing.is_reels = True
            if existing.slug != "reels":
                existing.slug = "reels"
            await session.commit()
            return

        session.add(
            Category(
                name="Reels",
                slug="reels",
                description="Watch product videos and shop from Reels",
                is_active=True,
                position=2,
                is_reels=True,
            )
        )
        await session.commit()
        print("Reels category seeded")


async def seed_default_categories():
    """Seed default cookware categories and map existing products."""
    import re

    from sqlalchemy import select, update

    from app.models import Category, Product

    def _slugify(name: str) -> str:
        s = name.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_-]+", "-", s)
        return s

    defaults = [
        {"name": "Tawas", "position": 0},
        {"name": "Kadhai", "position": 1},
        {"name": "Skillets", "position": 2},
        {"name": "Utensils", "position": 3},
        {"name": "Cast Iron Sets", "position": 4},
    ]

    async with AsyncSessionLocal() as session:
        for cat_data in defaults:
            existing = (
                await session.execute(
                    select(Category).where(Category.name == cat_data["name"])
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(
                    Category(
                        name=cat_data["name"],
                        slug=_slugify(cat_data["name"]),
                        is_active=True,
                        position=cat_data["position"],
                    )
                )

        await session.commit()

        result = await session.execute(select(Category))
        for cat in result.scalars().all():
            await session.execute(
                update(Product)
                .where(Product.category.ilike(cat.name))
                .where(Product.category_id.is_(None))
                .values(category_id=cat.id, category=cat.name)
            )

        await session.commit()
        print("Default categories seeded")
