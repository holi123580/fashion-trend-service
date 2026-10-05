"""Pydantic 请求/响应 Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== Source =====
class SourceBase(BaseModel):
    name: str
    type: str
    url: str
    region: str = "global"
    language: str = "en"
    enabled: bool = True


class SourceCreate(SourceBase):
    pass


class SourceResponse(SourceBase):
    id: int
    last_fetched_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Creator =====
class CreatorBase(BaseModel):
    platform: str
    username: str
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    followers: int = 0
    region: str = "global"
    style_tags: List[str] = []
    bio: Optional[str] = None


class CreatorCreate(CreatorBase):
    pass


class CreatorResponse(CreatorBase):
    id: int
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Post =====
class PostBase(BaseModel):
    platform: str
    title: Optional[str] = None
    summary: Optional[str] = None
    image_urls: List[str] = []
    original_url: str
    likes: int = 0
    favorites: int = 0
    comments: int = 0
    shares: int = 0
    published_at: Optional[datetime] = None
    region: str = "global"
    style_tags: List[str] = []


class PostCreate(PostBase):
    creator_id: Optional[int] = None
    source_id: Optional[int] = None


class PostResponse(PostBase):
    id: int
    creator_id: Optional[int] = None
    source_id: Optional[int] = None
    created_at: datetime
    creator: Optional[CreatorResponse] = None

    class Config:
        from_attributes = True


# ===== OutfitItem =====
class OutfitItemBase(BaseModel):
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    image_url: Optional[str] = None
    purchase_url: Optional[str] = None
    price: Optional[str] = None


class OutfitItemCreate(OutfitItemBase):
    pass


class OutfitItemResponse(OutfitItemBase):
    id: int
    outfit_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Outfit =====
class OutfitBase(BaseModel):
    outfit_image_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    brands: List[str] = []
    style_tags: List[str] = []
    season: Optional[str] = None
    region: str = "global"
    likes: int = 0
    published_at: Optional[datetime] = None


class OutfitCreate(OutfitBase):
    post_id: Optional[int] = None
    items: List[OutfitItemCreate] = []


class OutfitResponse(OutfitBase):
    id: int
    post_id: Optional[int] = None
    items: List[OutfitItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ===== TrendSignal =====
class TrendSignalResponse(BaseModel):
    id: int
    region: str
    style: Optional[str] = None
    keyword: Optional[str] = None
    heat_score: float
    followers_count: int
    likes_count: int
    sales_count: int
    post_count: int
    calculated_at: datetime
    time_window_days: int

    class Config:
        from_attributes = True


# ===== MagazineArticle =====
class MagazineArticleBase(BaseModel):
    magazine_name: str
    title: str
    summary: Optional[str] = None
    cover_image_url: Optional[str] = None
    original_url: str
    published_at: Optional[datetime] = None
    tags: List[str] = []
    author: Optional[str] = None
    region: str = "global"


class MagazineArticleCreate(MagazineArticleBase):
    source_id: Optional[int] = None


class MagazineArticleResponse(MagazineArticleBase):
    id: int
    source_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== API 请求 =====
class RefreshRequest(BaseModel):
    sources: Optional[List[str]] = None  # 指定来源名称，不传则全部
    force: bool = False


class AIStylingRequest(BaseModel):
    wardrobe_items: List[Dict[str, Any]] = Field(..., description="用户衣柜单品列表")
    region: str = "global"
    style: Optional[str] = None
    occasion: Optional[str] = None
    season: Optional[str] = None


class AIStylingOutfit(BaseModel):
    trend_source: str
    suitable_scene: str
    wardrobe_items_to_use: List[str]
    missing_items: List[str]
    alternative_brands: List[str]
    color_palette: List[str]
    description: str


class AIStylingResponse(BaseModel):
    outfits: List[AIStylingOutfit]
    trend_summary: str
    sources: List[str]


# ===== 通用响应 =====
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
