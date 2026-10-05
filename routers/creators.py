"""创作者/博主API路由"""
from fastapi import APIRouter, Query, HTTPException

from services.trend_service import trend_service

router = APIRouter(prefix="/api/creators", tags=["creators"])


@router.get("")
async def get_creators(
    platform: str = Query(None, description="平台: youtube/pinterest/tiktok/wear/musinsa/instagram/lemon8"),
    sort: str = Query("followers", description="排序: followers/likes"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取全球最受欢迎的时尚博主列表

    支持按平台筛选，按粉丝量/总点赞量排序。
    每个卡片显示：头像、用户名、平台、粉丝数、地区、风格标签。
    """
    if sort not in ("followers", "likes"):
        raise HTTPException(status_code=400, detail="sort must be one of: followers, likes")

    creators, total = trend_service.get_creators(
        platform=platform,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": c.id,
                "platform": c.platform,
                "username": c.username,
                "display_name": c.display_name,
                "profile_url": c.profile_url,
                "avatar_url": c.avatar_url,
                "followers": c.followers,
                "region": c.region,
                "style_tags": c.style_tags,
                "bio": c.bio,
                "last_updated": c.last_updated,
            }
            for c in creators
        ],
        "total": total,
        "page": offset // limit + 1,
        "page_size": limit,
    }
