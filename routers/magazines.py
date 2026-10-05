"""杂志资讯API路由"""
from fastapi import APIRouter, Query

from services.trend_service import trend_service

router = APIRouter(prefix="/api/magazines", tags=["magazines"])


@router.get("/latest")
async def get_latest_magazines(
    source: str = Query(None, description="杂志名称筛选: Vogue US/Vogue UK/Hypebeast/WWD/BoF/Highsnobiety等"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取最新杂志文章/资讯

    支持按杂志来源筛选，按发布时间倒序。
    每个卡片显示：封面图、杂志名、标题、摘要、作者、发布时间、原文链接、标签。
    只存储摘要和封面图URL，不存储完整版权文章。
    """
    articles, total = trend_service.get_magazine_articles(
        source=source,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": a.id,
                "magazine_name": a.magazine_name,
                "title": a.title,
                "summary": a.summary,
                "cover_image_url": a.cover_image_url,
                "original_url": a.original_url,
                "published_at": a.published_at,
                "tags": a.tags,
                "author": a.author,
                "region": a.region,
            }
            for a in articles
        ],
        "total": total,
        "page": offset // limit + 1,
        "page_size": limit,
    }


@router.get("/sources")
async def get_magazine_sources():
    """获取可用的杂志来源列表"""
    from adapters.rss import PRESET_RSS_FEEDS

    sources = []
    for key, config in PRESET_RSS_FEEDS.items():
        sources.append({
            "key": key,
            "name": config["name"],
            "region": config["region"],
            "language": config["language"],
            "type": config["type"],
            "url": config["url"],
        })

    return {"sources": sources, "total": len(sources)}
