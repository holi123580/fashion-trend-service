"""采集适配器基类 - 统一接口"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FetchResult:
    """采集结果统一格式"""
    source_name: str
    source_type: str  # rss / apify / api / scraper
    region: str = "global"
    posts: List[Dict[str, Any]] = field(default_factory=list)
    creators: List[Dict[str, Any]] = field(default_factory=list)
    outfits: List[Dict[str, Any]] = field(default_factory=list)
    magazine_articles: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def has_data(self) -> bool:
        return any([self.posts, self.creators, self.outfits, self.magazine_articles])


class BaseAdapter(ABC):
    """采集适配器抽象基类"""

    def __init__(self, source_name: str, region: str = "global", **kwargs):
        self.source_name = source_name
        self.region = region
        self.config = kwargs

    @abstractmethod
    async def fetch(self, **kwargs) -> FetchResult:
        """
        执行采集，返回统一格式的FetchResult。
        所有适配器必须实现此方法。
        """
        pass

    def get_headers(self) -> Dict[str, str]:
        """获取请求头，包含合规的User-Agent"""
        return {
            "User-Agent": self.config.get(
                "user_agent",
                "SmartWardrobe-TrendBot/1.0 (compatible; +https://example.com/bot)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def check_robots_txt(self, base_url: str) -> bool:
        """
        检查robots.txt是否允许爬取。
        返回True表示允许，False表示禁止。
        合规底线：必须遵守robots.txt。
        """
        try:
            import httpx
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(robots_url, headers=self.get_headers())
                if resp.status_code == 200:
                    content = resp.text
                    # 简单解析：检查是否有Disallow针对我们的UA或全部
                    for line in content.split("\n"):
                        line = line.strip().lower()
                        if line.startswith("disallow:") and ("*" in line or "smartwardrobe" in line):
                            path = line.split("disallow:", 1)[1].strip()
                            if path == "/" or path == "":
                                return False
            return True
        except Exception:
            # robots.txt无法获取时，保守起见允许采集公开页面
            return True
