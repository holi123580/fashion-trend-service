"""AI服务 - 基于趋势数据+用户衣柜生成搭配灵感"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from config import settings
from services.trend_service import trend_service


# AI系统提示词 - 电子衣柜全球时尚趋势助手
AI_SYSTEM_PROMPT = """你是电子衣柜的全球时尚趋势助手。用户询问最新穿搭、博主、杂志或搭配灵感时，必须调用工具获取实时数据，不得编造。回答必须标注来源、日期、粉丝/点赞/销量依据。生成灵感时，结合用户衣柜已有单品，输出 3 套方案，每套包含：趋势来源、适合场景、用我衣柜里哪些单品复刻、还缺什么单品、可替换品牌。只使用工具返回的图片链接和摘要，不复制完整版权内容。"""


class AIService:
    """AI搭配灵感服务

    支持两种模式：
    1. 有AI API Key时，调用外部AI生成搭配灵感
    2. 无AI API Key时，使用基于规则的本地算法生成搭配灵感
    """

    def __init__(self):
        self.api_key = settings.AI_API_KEY
        self.api_base = settings.AI_API_BASE
        self.model = settings.AI_MODEL

    async def generate_styling_inspiration(
        self,
        wardrobe_items: List[Dict[str, Any]],
        region: str = "global",
        style: Optional[str] = None,
        occasion: Optional[str] = None,
        season: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成搭配灵感

        Args:
            wardrobe_items: 用户衣柜单品列表
            region: 地区
            style: 风格偏好
            occasion: 场合
            season: 季节

        Returns:
            搭配灵感结果
        """
        # 获取当前趋势数据
        outfits, _ = trend_service.get_outfits(
            region=region,
            sort_by="heat",
            days=7,
            style=style,
            limit=10,
        )

        trend_signals = trend_service.get_trend_signals(region=region, limit=5)

        # 构建趋势摘要
        trend_summary = self._build_trend_summary(outfits, trend_signals)

        # 如果有AI API Key，调用外部AI
        if self.api_key:
            return await self._generate_with_ai(
                wardrobe_items=wardrobe_items,
                outfits=outfits,
                trend_summary=trend_summary,
                region=region,
                style=style,
                occasion=occasion,
                season=season,
            )

        # 否则使用本地规则算法
        return self._generate_with_rules(
            wardrobe_items=wardrobe_items,
            outfits=outfits,
            trend_summary=trend_summary,
            region=region,
            style=style,
            occasion=occasion,
            season=season,
        )

    def _build_trend_summary(self, outfits: List, trend_signals: List) -> str:
        """构建趋势摘要"""
        parts = []

        if trend_signals:
            top_signals = trend_signals[:3]
            signal_desc = ", ".join([
                f"{s.style or s.keyword}(热度{s.heat_score})"
                for s in top_signals
            ])
            parts.append(f"当前热门风格: {signal_desc}")

        if outfits:
            top_outfits = outfits[:5]
            outfit_desc = ", ".join([
                f"{o.title or '搭配'}(点赞{o.likes})"
                for o in top_outfits if o.title
            ])
            if outfit_desc:
                parts.append(f"热门搭配: {outfit_desc}")

            # 提取品牌
            brands = set()
            for o in top_outfits:
                if o.brands:
                    brands.update(o.brands)
            if brands:
                parts.append(f"热门品牌: {', '.join(list(brands)[:5])}")

        return "; ".join(parts) if parts else "暂无趋势数据"

    async def _generate_with_ai(
        self,
        wardrobe_items: List[Dict],
        outfits: List,
        trend_summary: str,
        region: str,
        style: Optional[str],
        occasion: Optional[str],
        season: Optional[str],
    ) -> Dict[str, Any]:
        """使用外部AI生成搭配灵感"""
        try:
            import httpx

            # 构建用户衣柜摘要
            wardrobe_summary = json.dumps([
                {
                    "name": item.get("name", ""),
                    "category": item.get("category", ""),
                    "color": item.get("color", ""),
                    "brand": item.get("brand", ""),
                    "season": item.get("season", ""),
                }
                for item in wardrobe_items[:30]  # 限制数量避免token过长
            ], ensure_ascii=False)

            # 构建趋势参考
            trend_references = json.dumps([
                {
                    "title": o.title,
                    "description": o.description,
                    "brands": o.brands,
                    "style_tags": o.style_tags,
                    "likes": o.likes,
                    "image_url": o.outfit_image_url,
                }
                for o in outfits[:5]
            ], ensure_ascii=False)

            user_prompt = f"""请基于以下信息，为用户生成3套搭配灵感方案。

【用户衣柜单品】
{wardrobe_summary}

【当前时尚趋势参考】
{trend_references}

【趋势摘要】
{trend_summary}

【用户偏好】
- 地区: {region}
- 风格: {style or '不限'}
- 场合: {occasion or '日常'}
- 季节: {season or '当季'}

请输出JSON格式，包含：
{{
  "outfits": [
    {{
      "trend_source": "趋势来源说明",
      "suitable_scene": "适合场景",
      "wardrobe_items_to_use": ["用衣柜里哪些单品"],
      "missing_items": ["还缺什么单品"],
      "alternative_brands": ["可替换品牌"],
      "color_palette": ["主色调"],
      "description": "搭配描述"
    }}
  ],
  "trend_summary": "趋势总结",
  "sources": ["数据来源"]
}}"""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": AI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            }

            api_url = f"{self.api_base.rstrip('/')}/chat/completions" if self.api_base else "https://api.openai.com/v1/chat/completions"

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()

            content = result["choices"][0]["message"]["content"]

            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    parsed = json.loads(content[json_start:json_end])
                    return parsed
            except Exception:
                pass

            # 解析失败，返回原始文本
            return {
                "outfits": [],
                "trend_summary": content,
                "sources": ["AI生成"],
            }

        except Exception as e:
            # AI调用失败，降级到本地规则
            return self._generate_with_rules(
                wardrobe_items=wardrobe_items,
                outfits=outfits,
                trend_summary=trend_summary,
                region=region,
                style=style,
                occasion=occasion,
                season=season,
            )

    def _generate_with_rules(
        self,
        wardrobe_items: List[Dict],
        outfits: List,
        trend_summary: str,
        region: str,
        style: Optional[str],
        occasion: Optional[str],
        season: Optional[str],
    ) -> Dict[str, Any]:
        """基于规则的本地搭配灵感生成算法"""
        # 按品类分组衣柜单品
        categorized = {"outer": [], "top": [], "bottom": [], "shoes": [], "accessory": []}
        for item in wardrobe_items:
            cat = item.get("category", "top")
            if cat in categorized:
                categorized[cat].append(item)

        # 从趋势中提取热门颜色和品牌
        trend_colors = set()
        trend_brands = set()
        for o in outfits:
            if o.brands:
                trend_brands.update(o.brands)
            if o.style_tags:
                trend_colors.update([t for t in o.style_tags if "色" in t or "color" in t.lower()])

        # 生成3套方案
        generated_outfits = []

        # 方案1：经典基础款搭配
        if categorized["top"] and categorized["bottom"]:
            top = categorized["top"][0]
            bottom = categorized["bottom"][0]
            outfit1 = {
                "trend_source": f"基于{region}地区经典百搭趋势，参考{outfits[0].title if outfits else '热门搭配'}",
                "suitable_scene": occasion or "日常通勤/休闲",
                "wardrobe_items_to_use": [top.get("name", ""), bottom.get("name", "")],
                "missing_items": [
                    f"建议补充一件{ '外套' if not categorized['outer'] else '配饰'}提升层次感"
                ] if not categorized["outer"] else ["可添加配饰点缀"],
                "alternative_brands": list(trend_brands)[:3] if trend_brands else ["优衣库", "ZARA", "COS"],
                "color_palette": [top.get("color", "中性色"), bottom.get("color", "深色")],
                "description": f"以{top.get('color', '')}{top.get('name', '上装')}搭配{bottom.get('color', '')}{bottom.get('name', '下装')}，简洁利落，适合{occasion or '日常'}。",
            }
            generated_outfits.append(outfit1)

        # 方案2：趋势风格搭配
        if outfits and len(categorized["top"]) > 1:
            trend_outfit = outfits[0]
            top2 = categorized["top"][1] if len(categorized["top"]) > 1 else categorized["top"][0]
            bottom2 = categorized["bottom"][1] if len(categorized["bottom"]) > 1 else (categorized["bottom"][0] if categorized["bottom"] else None)
            outer2 = categorized["outer"][0] if categorized["outer"] else None

            items_to_use = [top2.get("name", "")]
            if bottom2:
                items_to_use.append(bottom2.get("name", ""))
            if outer2:
                items_to_use.append(outer2.get("name", ""))

            outfit2 = {
                "trend_source": f"参考热门搭配「{trend_outfit.title or '趋势搭配'}」(点赞{trend_outfit.likes})",
                "suitable_scene": f"{style or '时尚'}风格出街/约会",
                "wardrobe_items_to_use": items_to_use,
                "missing_items": [
                    f"趋势热门单品: {', '.join(trend_outfit.brands[:2]) if trend_outfit.brands else ' statement piece'}"
                ],
                "alternative_brands": list(trend_brands)[:3] if trend_brands else ["&Other Stories", "Mango", "Massimo Dutti"],
                "color_palette": list(trend_colors)[:3] if trend_colors else [top2.get("color", "流行色")],
                "description": f"借鉴{trend_outfit.title or '热门趋势'}的搭配思路，用你衣柜中的{', '.join(items_to_use)}复刻类似风格。",
            }
            generated_outfits.append(outfit2)

        # 方案3：叠穿层次感搭配
        if categorized["outer"] and categorized["top"] and categorized["bottom"]:
            outer3 = categorized["outer"][0]
            top3 = categorized["top"][0]
            bottom3 = categorized["bottom"][0]
            shoes3 = categorized["shoes"][0] if categorized["shoes"] else None

            items3 = [outer3.get("name", ""), top3.get("name", ""), bottom3.get("name", "")]
            if shoes3:
                items3.append(shoes3.get("name", ""))

            outfit3 = {
                "trend_source": f"基于{season or '当季'}叠穿趋势，{region}地区热门层次搭配法",
                "suitable_scene": "温差较大的春秋季/商务休闲",
                "wardrobe_items_to_use": items3,
                "missing_items": ["可添加围巾/帽子等配饰增加细节感"],
                "alternative_brands": list(trend_brands)[:3] if trend_brands else ["Theory", "Max Mara", "Weekday"],
                "color_palette": [outer3.get("color", ""), top3.get("color", ""), bottom3.get("color", "")],
                "description": f"{outer3.get('name', '外套')}+{top3.get('name', '内搭')}+{bottom3.get('name', '下装')}的三层叠穿，利用色彩对比营造层次感。",
            }
            generated_outfits.append(outfit3)

        # 如果不足3套，补充通用建议
        while len(generated_outfits) < 3:
            idx = len(generated_outfits) + 1
            generated_outfits.append({
                "trend_source": f"通用搭配方案{idx}",
                "suitable_scene": "多种场合",
                "wardrobe_items_to_use": [item.get("name", "") for item in wardrobe_items[:2]],
                "missing_items": ["建议丰富衣柜品类，增加更多搭配可能性"],
                "alternative_brands": ["优衣库", "ZARA", "H&M"],
                "color_palette": ["中性色", "基础色"],
                "description": f"基础搭配方案{idx}，以简洁百搭为主。",
            })

        return {
            "outfits": generated_outfits[:3],
            "trend_summary": trend_summary,
            "sources": [
                f"趋势数据: {len(outfits)}套热门搭配",
                f"衣柜单品: {len(wardrobe_items)}件",
                "生成方式: 本地规则算法(未配置AI API Key)" if not self.api_key else "AI生成(降级)",
            ],
        }


# 全局单例
ai_service = AIService()
