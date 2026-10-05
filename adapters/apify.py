"""Apify采集适配器 - 无官方API时使用Apify现成Actor

支持的Apify Actor：
- Lemon8 Scraper
- WEAR (ZOZO) Fashion Coordinate Scraper
- Musinsa Scraper
- Website Image Downloader
- Instagram Scraper (可选)
- TikTok Scraper (可选)

合规说明：
- Apify Actor遵守目标网站ToS
- 只存储元数据、摘要、缩略图URL、原文链接
- 不绕过登录墙、验证码、付费墙
- 需要配置APIFY_TOKEN
"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from adapters.base import BaseAdapter, FetchResult


# 预设的Apify Actor配置
PRESET_APIFY_ACTORS = {
    "lemon8": {
        "name": "Lemon8 Scraper",
        "actor_id": "lemon8-scraper",  # 需要替换为实际Actor ID
        "region": "global",
        "platform": "lemon8",
        "default_input": {
            "search": "fashion outfit",
            "maxItems": 20,
        },
    },
    "wear": {
        "name": "WEAR (ZOZO) Fashion Coordinate Scraper",
        "actor_id": "wear-zozo-scraper",  # 需要替换为实际Actor ID
        "region": "jp",
        "platform": "wear",
        "default_input": {
            "search": "coordinate",
            "maxItems": 20,
        },
    },
    "musinsa": {
        "name": "Musinsa Scraper",
        "actor_id": "musinsa-scraper",  # 需要替换为实际Actor ID
        "region": "kr",
        "platform": "musinsa",
        "default_input": {
            "search": "fashion",
            "maxItems": 20,
        },
    },
    "website_images": {
        "name": "Website Image Downloader",
        "actor_id": "website-image-downloader",  # 需要替换为实际Actor ID
        "region": "global",
        "platform": "generic",
        "default_input": {
            "startUrls": [],
            "maxImages": 50,
        },
    },
}


class ApifyAdapter(BaseAdapter):
    """Apify采集适配器

    使用Apify平台的现成Actor进行数据采集。
    需要配置APIFY_TOKEN环境变量。
    """

    API_BASE = "https://api.apify.com/v2"

    def __init__(
        self,
        actor_key: str,
        api_token: Optional[str] = None,
        custom_actor_id: Optional[str] = None,
        **kwargs,
    ):
        actor_config = PRESET_APIFY_ACTORS.get(actor_key, {})
        name = actor_config.get("name", actor_key)
        region = actor_config.get("region", "global")
        super().__init__(source_name=name, region=region, **kwargs)
        self.actor_key = actor_key
        self.actor_id = custom_actor_id or actor_config.get("actor_id", "")
        self.platform = actor_config.get("platform", "generic")
        self.default_input = actor_config.get("default_input", {})
        self.api_token = api_token or kwargs.get("APIFY_TOKEN", "")

    async def fetch(self, run_input: Optional[Dict] = None, **kwargs) -> FetchResult:
        """执行Apify Actor采集"""
        result = FetchResult(
            source_name=self.source_name,
            source_type="apify",
            region=self.region,
        )

        if not self.api_token:
            result.error = "APIFY_TOKEN not configured. Set APIFY_TOKEN environment variable."
            return result

        if not self.actor_id:
            result.error = f"Apify Actor ID not configured for {self.actor_key}"
            return result

        try:
            # 合并输入参数
            final_input = {**self.default_input, **(run_input or {})}

            # 启动Actor运行
            run_url = f"{self.API_BASE}/acts/{self.actor_id}/runs"
            async with httpx.AsyncClient(
                timeout=self.config.get("timeout", 60),
                follow_redirects=True,
            ) as client:
                # 启动运行
                resp = await client.post(
                    run_url,
                    params={"token": self.api_token},
                    json=final_input,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                run_data = resp.json()
                run_id = run_data.get("data", {}).get("id", "")

                if not run_id:
                    result.error = "Failed to start Apify Actor run"
                    return result

                # 等待运行完成（轮询）
                dataset_id = await self._wait_for_run(client, run_id)
                if not dataset_id:
                    result.error = "Apify Actor run timed out or failed"
                    return result

                # 获取结果数据
                items = await self._get_dataset_items(client, dataset_id)

            # 解析结果
            self._parse_results(items, result)

        except httpx.HTTPStatusError as e:
            result.error = f"Apify API HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            result.error = f"Apify fetch failed: {str(e)}"

        return result

    async def _wait_for_run(self, client: httpx.AsyncClient, run_id: str, timeout: int = 120) -> Optional[str]:
        """等待Apify Actor运行完成，返回dataset_id"""
        import asyncio
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).seconds < timeout:
            status_url = f"{self.API_BASE}/actor-runs/{run_id}"
            resp = await client.get(
                status_url,
                params={"token": self.api_token},
            )
            if resp.status_code == 200:
                run_info = resp.json().get("data", {})
                status = run_info.get("status", "")

                if status == "SUCCEEDED":
                    return run_info.get("defaultDatasetId", "")
                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    return None

            await asyncio.sleep(3)

        return None

    async def _get_dataset_items(self, client: httpx.AsyncClient, dataset_id: str, limit: int = 100) -> List[Dict]:
        """获取Apify数据集条目"""
        items_url = f"{self.API_BASE}/datasets/{dataset_id}/items"
        resp = await client.get(
            items_url,
            params={"token": self.api_token, "limit": limit},
        )
        if resp.status_code == 200:
            return resp.json()
        return []

    def _parse_results(self, items: List[Dict], result: FetchResult):
        """解析Apify返回的数据，统一格式"""
        for item in items:
            # 根据不同平台解析
            if self.platform == "wear":
                self._parse_wear_item(item, result)
            elif self.platform == "musinsa":
                self._parse_musinsa_item(item, result)
            elif self.platform == "lemon8":
                self._parse_lemon8_item(item, result)
            else:
                self._parse_generic_item(item, result)

    def _parse_wear_item(self, item: Dict, result: FetchResult):
        """解析WEAR平台数据"""
        post_data = {
            "platform": "wear",
            "title": item.get("title", "") or item.get("description", "")[:100],
            "summary": item.get("description", "")[:300],
            "image_urls": item.get("images", []) or ([item.get("imageUrl", "")] if item.get("imageUrl") else []),
            "original_url": item.get("url", ""),
            "likes": item.get("likes", 0) or item.get("likeCount", 0),
            "favorites": item.get("favorites", 0),
            "comments": item.get("comments", 0) or item.get("commentCount", 0),
            "published_at": self._parse_date(item.get("publishedAt") or item.get("date")),
            "region": "jp",
            "style_tags": item.get("tags", []),
        }
        result.posts.append(post_data)

        # WEAR的搭配数据
        if item.get("items") or item.get("coordinateItems"):
            outfit_data = {
                "outfit_image_url": post_data["image_urls"][0] if post_data["image_urls"] else None,
                "title": post_data["title"],
                "description": post_data["summary"],
                "brands": item.get("brands", []),
                "style_tags": post_data["style_tags"],
                "season": item.get("season"),
                "region": "jp",
                "likes": post_data["likes"],
                "published_at": post_data["published_at"],
                "items": self._parse_outfit_items(item.get("items") or item.get("coordinateItems", [])),
            }
            result.outfits.append(outfit_data)

        # 创作者信息
        if item.get("user") or item.get("author"):
            user = item.get("user") or item.get("author", {})
            creator_data = {
                "platform": "wear",
                "username": user.get("username", "") or user.get("id", ""),
                "display_name": user.get("displayName", "") or user.get("name", ""),
                "profile_url": user.get("profileUrl", ""),
                "avatar_url": user.get("avatarUrl", ""),
                "followers": user.get("followers", 0) or user.get("followerCount", 0),
                "region": "jp",
                "style_tags": user.get("tags", []),
            }
            result.creators.append(creator_data)

    def _parse_musinsa_item(self, item: Dict, result: FetchResult):
        """解析Musinsa平台数据"""
        post_data = {
            "platform": "musinsa",
            "title": item.get("title", "") or item.get("name", ""),
            "summary": item.get("description", "")[:300],
            "image_urls": item.get("images", []) or ([item.get("imageUrl", "")] if item.get("imageUrl") else []),
            "original_url": item.get("url", ""),
            "likes": item.get("likes", 0) or item.get("likeCount", 0),
            "favorites": item.get("favorites", 0),
            "comments": item.get("comments", 0),
            "published_at": self._parse_date(item.get("date") or item.get("publishedAt")),
            "region": "kr",
            "style_tags": item.get("tags", []),
        }
        result.posts.append(post_data)

    def _parse_lemon8_item(self, item: Dict, result: FetchResult):
        """解析Lemon8平台数据"""
        post_data = {
            "platform": "lemon8",
            "title": item.get("title", ""),
            "summary": item.get("content", "")[:300] or item.get("description", "")[:300],
            "image_urls": item.get("images", []) or ([item.get("imageUrl", "")] if item.get("imageUrl") else []),
            "original_url": item.get("url", ""),
            "likes": item.get("likes", 0) or item.get("likeCount", 0),
            "favorites": item.get("favorites", 0) or item.get("saveCount", 0),
            "comments": item.get("comments", 0) or item.get("commentCount", 0),
            "published_at": self._parse_date(item.get("createdAt") or item.get("date")),
            "region": "global",
            "style_tags": item.get("tags", []),
        }
        result.posts.append(post_data)

    def _parse_generic_item(self, item: Dict, result: FetchResult):
        """解析通用数据"""
        post_data = {
            "platform": self.platform,
            "title": item.get("title", "") or item.get("name", ""),
            "summary": item.get("description", "")[:300] or item.get("content", "")[:300],
            "image_urls": item.get("images", []) or item.get("imageUrls", []) or ([item.get("imageUrl", "")] if item.get("imageUrl") else []),
            "original_url": item.get("url", "") or item.get("link", ""),
            "likes": item.get("likes", 0),
            "favorites": item.get("favorites", 0),
            "comments": item.get("comments", 0),
            "published_at": self._parse_date(item.get("date") or item.get("publishedAt")),
            "region": self.region,
            "style_tags": item.get("tags", []),
        }
        if post_data["title"] or post_data["original_url"]:
            result.posts.append(post_data)

    def _parse_outfit_items(self, items: List[Dict]) -> List[Dict]:
        """解析搭配单品列表"""
        result = []
        for item in items:
            result.append({
                "name": item.get("name", "") or item.get("title", ""),
                "brand": item.get("brand", ""),
                "category": item.get("category", ""),
                "color": item.get("color", ""),
                "image_url": item.get("imageUrl", "") or item.get("image", ""),
                "purchase_url": item.get("url", "") or item.get("purchaseUrl", ""),
                "price": item.get("price", ""),
            })
        return result

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            from dateutil import parser as date_parser
            return date_parser.parse(date_str)
        except Exception:
            return None
