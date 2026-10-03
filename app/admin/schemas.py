from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.common import validate_person_name


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: dict


class AdminProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None


class CustomOrderCustomer(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=10, max_length=15)
    email: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _real_name(cls, value: str) -> str:
        return validate_person_name(value)


class CustomOrderAddress(BaseModel):
    line1: str = Field(..., min_length=3)
    line2: Optional[str] = None
    landmark: Optional[str] = None
    city: str = Field(..., min_length=2)
    state: str = Field(..., min_length=2)
    pincode: str = Field(..., min_length=6, max_length=6)


class CustomOrderRequest(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1, le=999)
    shipping_charge: float = Field(..., ge=0)
    payment_type: str = Field(..., description="cod | paid")
    customer: CustomOrderCustomer
    address: CustomOrderAddress


class TokenData(BaseModel):
    admin_id: str
    email: str
    role: str


class ProductVariantOption(BaseModel):
    name: str
    price: float
    mrp: float
    stock: int
    weight: Optional[float] = None


class ProductVariant(BaseModel):
    name: str
    options: list[ProductVariantOption]


class ProductCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    price: float
    mrp: float
    category: str = ""
    category_id: Optional[int] = None
    stock: int = 0
    unit: Optional[str] = "grams"
    weight: Optional[float] = None
    length_cm: Optional[float] = None
    breadth_cm: Optional[float] = None
    height_cm: Optional[float] = None
    is_featured: bool = False
    is_active: bool = True
    variants: Optional[list[ProductVariant]] = []
    tags: Optional[list[str]] = []
    metafields: Optional[dict[str, str]] = {}
    seo_title: Optional[str] = ""
    seo_description: Optional[str] = ""


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    category: Optional[str] = None
    category_id: Optional[int] = None
    stock: Optional[int] = None
    unit: Optional[str] = None
    weight: Optional[float] = None
    length_cm: Optional[float] = None
    breadth_cm: Optional[float] = None
    height_cm: Optional[float] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None
    variants: Optional[list[ProductVariant]] = None
    tags: Optional[list[str]] = None
    metafields: Optional[dict[str, str]] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    price: float
    mrp: float
    category: str
    stock: int
    unit: Optional[str]
    weight: Optional[float]
    images: list[str]
    is_featured: bool
    is_active: bool
    variants: Optional[list[ProductVariant]] = []
    tags: Optional[list[str]] = []
    metafields: Optional[dict[str, str]] = {}
    seo_title: Optional[str] = ""
    seo_description: Optional[str] = ""
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_products: int
    total_shipped: int
    recent_orders: list[Any]
    revenue_trend: list[Any]
