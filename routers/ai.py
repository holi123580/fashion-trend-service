"""AI搭配灵感API路由"""
from fastapi import APIRouter, HTTPException

from schemas import AIStylingRequest, AIStylingResponse
from services.ai_service import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/styling-inspiration")
async def generate_styling_inspiration(request: AIStylingRequest):
    """AI基于趋势数据+用户衣柜生成搭配灵感

    输入用户衣柜单品列表，结合当前全球时尚趋势，生成3套搭配方案。
    每套包含：趋势来源、适合场景、用衣柜里哪些单品复刻、还缺什么单品、可替换品牌、色彩方案。

    合规说明：
    - 只使用工具返回的图片链接和摘要，不复制完整版权内容
    - 所有AI生成内容标注来源和日期
    - 无AI API Key时自动降级为本地规则算法
    """
    if not request.wardrobe_items:
        raise HTTPException(status_code=400, detail="wardrobe_items is required")

    result = await ai_service.generate_styling_inspiration(
        wardrobe_items=request.wardrobe_items,
        region=request.region,
        style=request.style,
        occasion=request.occasion,
        season=request.season,
    )

    return result
