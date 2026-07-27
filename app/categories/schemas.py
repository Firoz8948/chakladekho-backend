from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CategoryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    is_active: bool = True
    position: int = 0


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None


class SubCategoryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    is_active: bool = True
    position: int = 0
    product_ids: Optional[List[int]] = Field(default_factory=list)


class SubCategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None
    product_ids: Optional[List[int]] = None


class SubCategoryResponse(BaseModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    position: int
    product_count: int = 0
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    image_url: Optional[str]
    is_active: bool
    position: int
    is_reels: bool = False
    subcategory_count: int = 0
    product_count: int = 0
    subcategories: Optional[List[SubCategoryResponse]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
