"""趋势相关API路由"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas import RefreshRequest, SuccessResponse, OutfitResponse, TrendSignalResponse
from services.trend_service import trend_service

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.post("/refresh", response_model=SuccessResponse)
async def refresh_trends(request: RefreshRequest):
    """手动触发采集

    - sources: 指定来源名称列表，不传则采集所有启用的来源
    - force: 是否强制刷新（忽略10分钟冷却）
    """
    result = await trend_service.refresh_trends(
        source_names=request.sources,
        force=request.force,
    )
    return SuccessResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        data=result,
    )


@router.get("/outfits")
async def get_outfits(
    region: str = Query("global", description="地区: global/us/uk/jp/kr/cn/eu"),
    sort: str = Query("likes", description="排序: followers/likes/sales/heat"),
    days: int = Query(7, ge=1, le=365, description="时间窗口（天）"),
    style: Optional[str] = Query(None, description="风格标签筛选"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取搭配列表

    支持按地区、风格、时间窗口筛选，按粉丝量/点赞量/销售量/综合热度排序。
    每个卡片包含：图片、来源、作者、粉丝/点赞/销量、日期、原文链接。
    """
    if sort not in ("followers", "likes", "sales", "heat"):
        raise HTTPException(status_code=400, detail="sort must be one of: followers, likes, sales, heat")

    outfits, total = trend_service.get_outfits(
        region=region,
        sort_by=sort,
        days=days,
        style=style,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": o.id,
                "title": o.title,
                "description": o.description,
                "outfit_image_url": o.outfit_image_url,
                "brands": o.brands,
                "style_tags": o.style_tags,
                "season": o.season,
                "region": o.region,
                "likes": o.likes,
                "published_at": o.published_at,
                "original_url": o.post.original_url if o.post else None,
                "creator": {
                    "username": o.post.creator.username if o.post and o.post.creator else None,
                    "display_name": o.post.creator.display_name if o.post and o.post.creator else None,
                    "followers": o.post.creator.followers if o.post and o.post.creator else None,
                    "platform": o.post.creator.platform if o.post and o.post.creator else None,
                } if o.post and o.post.creator else None,
                "items": [
                    {
                        "name": item.name,
                        "brand": item.brand,
                        "category": item.category,
                        "color": item.color,
                        "image_url": item.image_url,
                        "purchase_url": item.purchase_url,
                        "price": item.price,
                    }
                    for item in o.items
                ],
            }
            for o in outfits
        ],
        "total": total,
        "page": offset // limit + 1,
        "page_size": limit,
    }


@router.get("/signals")
async def get_trend_signals(
    region: str = Query("global", description="地区"),
    limit: int = Query(20, ge=1, le=100),
):
    """获取趋势信号（热度计算结果）

    返回按综合热度排序的趋势关键词/风格。
    综合热度 = 0.4*点赞归一化 + 0.3*粉丝归一化 + 0.2*销量归一化 + 0.1*时间新鲜度
    """
    signals = trend_service.get_trend_signals(region=region, limit=limit)
    return {
        "items": [
            {
                "id": s.id,
                "region": s.region,
                "style": s.style,
                "keyword": s.keyword,
                "heat_score": s.heat_score,
                "followers_count": s.followers_count,
                "likes_count": s.likes_count,
                "sales_count": s.sales_count,
                "post_count": s.post_count,
                "calculated_at": s.calculated_at,
                "time_window_days": s.time_window_days,
            }
            for s in signals
        ],
        "total": len(signals),
    }
