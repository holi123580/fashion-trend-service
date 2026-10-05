"""RSS采集适配器 - 全球时尚杂志/媒体优先用RSS

支持的RSS源：
- Vogue (US/UK/JP)
- Hypebeast
- WWD (Women's Wear Daily)
- Business of Fashion
- Highsnobiety
- 其他可配置的RSS源
"""
import httpx
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime
from dateutil import parser as date_parser
from adapters.base import BaseAdapter, FetchResult


# 预设的时尚媒体RSS源
PRESET_RSS_FEEDS = {
    "vogue_us": {
        "name": "Vogue US",
        "url": "https://www.vogue.com/feed/rss",
        "region": "us",
        "language": "en",
        "type": "magazine",
    },
    "vogue_uk": {
        "name": "Vogue UK",
        "url": "https://www.vogue.co.uk/feed/rss",
        "region": "uk",
        "language": "en",
        "type": "magazine",
    },
    "vogue_jp": {
        "name": "Vogue Japan",
        "url": "https://www.vogue.co.jp/rss",
        "region": "jp",
        "language": "ja",
        "type": "magazine",
    },
    "hypebeast": {
        "name": "Hypebeast",
        "url": "https://hypebeast.com/feed",
        "region": "global",
        "language": "en",
        "type": "media",
    },
    "wwd": {
        "name": "WWD",
        "url": "https://wwd.com/feed/",
        "region": "us",
        "language": "en",
        "type": "magazine",
    },
    "business_of_fashion": {
        "name": "Business of Fashion",
        "url": "https://www.businessoffashion.com/feed/",
        "region": "global",
        "language": "en",
        "type": "media",
    },
    "highsnobiety": {
        "name": "Highsnobiety",
        "url": "https://www.highsnobiety.com/feed/",
        "region": "global",
        "language": "en",
        "type": "media",
    },
    "fashionista": {
        "name": "Fashionista",
        "url": "https://fashionista.com/feed/rss",
        "region": "us",
        "language": "en",
        "type": "media",
    },
    "the_fashion_law": {
        "name": "The Fashion Law",
        "url": "https://thefashionlaw.com/feed/",
        "region": "global",
        "language": "en",
        "type": "media",
    },
    "wear_news": {
        "name": "WEAR News (JP)",
        "url": "https://wear.jp/news/rss/",
        "region": "jp",
        "language": "ja",
        "type": "community",
    },
}


class RSSAdapter(BaseAdapter):
    """RSS采集适配器

    合规说明：
    - RSS是官方提供的订阅源，属于公开API的一种
    - 只存储标题、摘要、图片URL、原文链接，不存储完整文章
    - 遵守目标网站ToS和robots.txt
    """

    def __init__(self, feed_key: str, custom_url: Optional[str] = None, **kwargs):
        feed_config = PRESET_RSS_FEEDS.get(feed_key, {})
        name = feed_config.get("name", feed_key)
        region = feed_config.get("region", "global")
        url = custom_url or feed_config.get("url", "")
        super().__init__(source_name=name, region=region, **kwargs)
        self.feed_url = url
        self.feed_key = feed_key
        self.feed_type = feed_config.get("type", "magazine")
        self.language = feed_config.get("language", "en")

    async def fetch(self, max_items: int = 20, **kwargs) -> FetchResult:
        """执行RSS采集"""
        result = FetchResult(
            source_name=self.source_name,
            source_type="rss",
            region=self.region,
        )

        if not self.feed_url:
            result.error = f"RSS URL not configured for {self.feed_key}"
            return result

        try:
            # 检查robots.txt
            from urllib.parse import urlparse
            parsed = urlparse(self.feed_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            if not await self.check_robots_txt(base_url):
                result.error = f"Blocked by robots.txt: {base_url}"
                return result

            # 获取RSS内容
            async with httpx.AsyncClient(
                timeout=self.config.get("timeout", 30),
                follow_redirects=True,
            ) as client:
                resp = await client.get(self.feed_url, headers=self.get_headers())
                resp.raise_for_status()
                content = resp.text

            # 解析RSS
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                result.error = f"RSS parse error: {feed.bozo_exception}"
                return result

            # 处理条目
            for i, entry in enumerate(feed.entries[:max_items]):
                # 解析发布时间
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_at = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                elif hasattr(entry, "published"):
                    try:
                        published_at = date_parser.parse(entry.published)
                    except Exception:
                        pass

                # 提取图片URL
                image_urls = self._extract_images(entry)

                # 提取摘要（截断，不存完整文章）
                summary = self._clean_summary(entry)

                # 提取作者
                author = getattr(entry, "author", None)

                # 提取标签
                tags = []
                if hasattr(entry, "tags"):
                    tags = [t.get("term", "") for t in entry.tags if t.get("term")]

                post_data = {
                    "platform": "rss",
                    "title": getattr(entry, "title", "")[:500],
                    "summary": summary,
                    "image_urls": image_urls,
                    "original_url": getattr(entry, "link", ""),
                    "likes": 0,  # RSS不提供互动数据
                    "favorites": 0,
                    "comments": 0,
                    "published_at": published_at,
                    "region": self.region,
                    "style_tags": tags[:10],
                    "author": author,
                }
                result.posts.append(post_data)

                # 如果是杂志类型，同时存入magazine_articles
                if self.feed_type in ("magazine", "media"):
                    article_data = {
                        "magazine_name": self.source_name,
                        "title": post_data["title"],
                        "summary": summary,
                        "cover_image_url": image_urls[0] if image_urls else None,
                        "original_url": post_data["original_url"],
                        "published_at": published_at,
                        "tags": tags[:10],
                        "author": author,
                        "region": self.region,
                    }
                    result.magazine_articles.append(article_data)

        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        except Exception as e:
            result.error = f"Fetch failed: {str(e)}"

        return result

    def _extract_images(self, entry) -> List[str]:
        """从RSS条目中提取图片URL"""
        images = []

        # 1. media:content
        if hasattr(entry, "media_content"):
            for media in entry.media_content:
                url = media.get("url", "")
                if url and url.startswith("http"):
                    images.append(url)

        # 2. media:thumbnail
        if hasattr(entry, "media_thumbnail"):
            for thumb in entry.media_thumbnail:
                url = thumb.get("url", "")
                if url and url.startswith("http") and url not in images:
                    images.append(url)

        # 3. 从content/summary中提取img标签
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary

        if content:
            import re
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
            for match in re.findall(img_pattern, content):
                if match.startswith("http") and match not in images:
                    images.append(match)

        return images[:5]  # 最多保留5张图

    def _clean_summary(self, entry) -> str:
        """清理并截断摘要，不存储完整版权文章"""
        import re
        summary = ""

        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description

        # 移除HTML标签
        summary = re.sub(r"<[^>]+>", " ", summary)
        # 移除多余空白
        summary = re.sub(r"\s+", " ", summary).strip()
        # 截断到300字符（只存摘要，不存完整文章）
        if len(summary) > 300:
            summary = summary[:300] + "..."

        return summary
