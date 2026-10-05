"""Fashion Trend Service 测试套件

覆盖：采集、排序、AI工具调用、衣柜匹配
运行：python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta
from database import Base, engine, SessionLocal
from models import Source, Creator, Post, Outfit, OutfitItem, TrendSignal, MagazineArticle


@pytest.fixture(scope="function")
def db_session():
    """每个测试使用独立的内存数据库"""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestModels:
    """数据库模型测试"""

    def test_create_source(self, db_session):
        source = Source(
            name="Test Vogue",
            type="rss",
            url="https://example.com/rss",
            region="us",
            language="en",
        )
        db_session.add(source)
        db_session.commit()
        assert source.id is not None
        assert source.name == "Test Vogue"
        assert source.enabled is True

    def test_create_creator(self, db_session):
        creator = Creator(
            platform="instagram",
            username="test_fashion_blogger",
            display_name="Test Blogger",
            followers=100000,
            region="us",
            style_tags=["streetwear", "minimalist"],
        )
        db_session.add(creator)
        db_session.commit()
        assert creator.id is not None
        assert creator.followers == 100000

    def test_create_post(self, db_session):
        creator = Creator(platform="test", username="user1", followers=100)
        source = Source(name="Test Source", type="rss", url="https://example.com")
        db_session.add_all([creator, source])
        db_session.flush()

        post = Post(
            creator_id=creator.id,
            source_id=source.id,
            platform="test",
            title="Test Post",
            summary="Test summary",
            image_urls=["https://example.com/img1.jpg"],
            original_url="https://example.com/post/1",
            likes=500,
            favorites=100,
            comments=50,
            published_at=datetime.utcnow(),
            region="global",
            style_tags=["casual"],
        )
        db_session.add(post)
        db_session.commit()
        assert post.id is not None
        assert post.likes == 500

    def test_create_outfit_with_items(self, db_session):
        outfit = Outfit(
            title="Test Outfit",
            description="Test description",
            brands=["Brand A", "Brand B"],
            style_tags=["streetwear"],
            season="spring",
            region="global",
            likes=1000,
        )
        db_session.add(outfit)
        db_session.flush()

        item1 = OutfitItem(
            outfit_id=outfit.id,
            name="Test Jacket",
            brand="Brand A",
            category="outer",
            color="black",
            image_url="https://example.com/jacket.jpg",
            purchase_url="https://example.com/buy",
            price="$100",
        )
        item2 = OutfitItem(
            outfit_id=outfit.id,
            name="Test Jeans",
            brand="Brand B",
            category="bottom",
            color="blue",
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        assert len(outfit.items) == 2
        assert outfit.items[0].name == "Test Jacket"

    def test_create_magazine_article(self, db_session):
        article = MagazineArticle(
            magazine_name="Vogue US",
            title="Test Article",
            summary="Test summary",
            cover_image_url="https://example.com/cover.jpg",
            original_url="https://example.com/article",
            published_at=datetime.utcnow(),
            tags=["fashion", "trends"],
            author="Test Author",
        )
        db_session.add(article)
        db_session.commit()
        assert article.id is not None

    def test_create_trend_signal(self, db_session):
        signal = TrendSignal(
            region="global",
            style="streetwear",
            keyword="oversized",
            heat_score=85.5,
            followers_count=10000,
            likes_count=50000,
            sales_count=0,
            post_count=100,
            time_window_days=7,
        )
        db_session.add(signal)
        db_session.commit()
        assert signal.heat_score == 85.5


class TestRSSAdapter:
    """RSS适配器测试"""

    def test_rss_adapter_initialization(self):
        from adapters.rss import RSSAdapter, PRESET_RSS_FEEDS
        adapter = RSSAdapter("vogue_us")
        assert adapter.source_name == "Vogue US"
        assert adapter.region == "us"
        assert adapter.feed_url == PRESET_RSS_FEEDS["vogue_us"]["url"]

    def test_rss_adapter_custom_url(self):
        from adapters.rss import RSSAdapter
        adapter = RSSAdapter("custom", custom_url="https://example.com/rss")
        assert adapter.feed_url == "https://example.com/rss"

    def test_preset_feeds_exist(self):
        from adapters.rss import PRESET_RSS_FEEDS
        required = ["vogue_us", "hypebeast", "wwd", "highsnobiety"]
        for key in required:
            assert key in PRESET_RSS_FEEDS
            assert "url" in PRESET_RSS_FEEDS[key]


class TestApifyAdapter:
    """Apify适配器测试"""

    def test_apify_adapter_initialization(self):
        from adapters.apify import ApifyAdapter
        adapter = ApifyAdapter("wear", api_token="test_token")
        assert adapter.source_name == "WEAR (ZOZO) Fashion Coordinate Scraper"
        assert adapter.region == "jp"
        assert adapter.api_token == "test_token"

    def test_apify_adapter_no_token(self):
        from adapters.apify import ApifyAdapter
        adapter = ApifyAdapter("wear")
        assert adapter.api_token == ""

    def test_preset_actors_exist(self):
        from adapters.apify import PRESET_APIFY_ACTORS
        required = ["lemon8", "wear", "musinsa", "website_images"]
        for key in required:
            assert key in PRESET_APIFY_ACTORS


class TestTrendService:
    """趋势服务测试"""

    def test_trend_service_singleton(self):
        from services.trend_service import trend_service
        assert trend_service is not None

    def test_cache_operations(self):
        from services.trend_service import TrendService
        service = TrendService()
        service._set_cache("test_key", {"data": 123}, ttl=60)
        cached = service._get_cache("test_key")
        assert cached == {"data": 123}

    def test_cache_expiry(self):
        from services.trend_service import TrendService
        service = TrendService()
        service._set_cache("expire_key", "data", ttl=-1)  # 已过期
        cached = service._get_cache("expire_key")
        assert cached is None

    def test_init_default_sources(self, db_session):
        from services.trend_service import trend_service
        trend_service.init_default_sources(db_session)
        sources = db_session.query(Source).all()
        assert len(sources) > 0
        # 验证Vogue存在
        vogue = db_session.query(Source).filter(Source.name.like("%Vogue%")).first()
        assert vogue is not None
        assert vogue.type == "rss"


class TestAIService:
    """AI服务测试"""

    def test_ai_service_singleton(self):
        from services.ai_service import ai_service
        assert ai_service is not None

    def test_system_prompt_contains_required_elements(self):
        from services.ai_service import AI_SYSTEM_PROMPT
        assert "电子衣柜" in AI_SYSTEM_PROMPT
        assert "全球时尚趋势助手" in AI_SYSTEM_PROMPT
        assert "必须调用工具" in AI_SYSTEM_PROMPT
        assert "3 套方案" in AI_SYSTEM_PROMPT

    def test_generate_with_rules_basic(self):
        """测试本地规则算法生成搭配灵感"""
        import asyncio
        from services.ai_service import AIService
        service = AIService()

        wardrobe_items = [
            {"name": "黑色西装外套", "category": "outer", "color": "黑色", "season": "spring"},
            {"name": "白色T恤", "category": "top", "color": "白色", "season": "all"},
            {"name": "深蓝色牛仔裤", "category": "bottom", "color": "深蓝", "season": "all"},
            {"name": "白色运动鞋", "category": "shoes", "color": "白色", "season": "all"},
        ]

        result = asyncio.run(service.generate_styling_inspiration(
            wardrobe_items=wardrobe_items,
            region="global",
            occasion="日常",
        ))

        assert "outfits" in result
        assert len(result["outfits"]) > 0
        assert "trend_summary" in result
        assert "sources" in result

        # 验证每套方案包含必要字段
        for outfit in result["outfits"]:
            assert "trend_source" in outfit
            assert "suitable_scene" in outfit
            assert "wardrobe_items_to_use" in outfit
            assert "missing_items" in outfit
            assert "alternative_brands" in outfit
            assert "color_palette" in outfit
            assert "description" in outfit

    def test_generate_with_rules_empty_wardrobe(self):
        """测试空衣柜时的处理"""
        import asyncio
        from services.ai_service import AIService
        service = AIService()

        result = asyncio.run(service.generate_styling_inspiration(
            wardrobe_items=[],
            region="global",
        ))

        assert "outfits" in result
        # 空衣柜时应该给出通用建议


class TestSorting:
    """排序算法测试"""

    def test_sort_by_followers(self, db_session):
        """测试按粉丝量排序"""
        c1 = Creator(platform="test", username="user1", followers=100)
        c2 = Creator(platform="test", username="user2", followers=500)
        c3 = Creator(platform="test", username="user3", followers=300)
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        from services.trend_service import trend_service
        creators, total = trend_service.get_creators(sort_by="followers", limit=10)
        assert total == 3
        assert creators[0].followers == 500
        assert creators[1].followers == 300
        assert creators[2].followers == 100

    def test_sort_by_likes(self, db_session):
        """测试按点赞量排序"""
        o1 = Outfit(title="Outfit 1", likes=100, published_at=datetime.utcnow())
        o2 = Outfit(title="Outfit 2", likes=500, published_at=datetime.utcnow())
        o3 = Outfit(title="Outfit 3", likes=300, published_at=datetime.utcnow())
        db_session.add_all([o1, o2, o3])
        db_session.commit()

        from services.trend_service import trend_service
        outfits, total = trend_service.get_outfits(sort_by="likes", days=365, limit=10)
        assert total == 3
        assert outfits[0].likes == 500

    def test_region_filter(self, db_session):
        """测试地区筛选"""
        o1 = Outfit(title="US Outfit", region="us", likes=100, published_at=datetime.utcnow())
        o2 = Outfit(title="JP Outfit", region="jp", likes=200, published_at=datetime.utcnow())
        o3 = Outfit(title="Global Outfit", region="global", likes=300, published_at=datetime.utcnow())
        db_session.add_all([o1, o2, o3])
        db_session.commit()

        from services.trend_service import trend_service
        outfits, total = trend_service.get_outfits(region="jp", sort_by="likes", days=365, limit=10)
        assert total == 1
        assert outfits[0].region == "jp"


class TestWardrobeMatching:
    """衣柜匹配测试"""

    def test_wardrobe_items_categorized(self):
        """测试衣柜单品分类"""
        import asyncio
        from services.ai_service import AIService
        service = AIService()

        wardrobe_items = [
            {"name": "外套1", "category": "outer"},
            {"name": "上衣1", "category": "top"},
            {"name": "下装1", "category": "bottom"},
            {"name": "鞋子1", "category": "shoes"},
            {"name": "配饰1", "category": "accessory"},
        ]

        result = asyncio.run(service.generate_styling_inspiration(
            wardrobe_items=wardrobe_items,
            region="global",
        ))

        # 验证生成的方案中引用了衣柜单品
        all_items = []
        for outfit in result["outfits"]:
            all_items.extend(outfit.get("wardrobe_items_to_use", []))

        # 至少有一些衣柜单品被引用
        assert len(all_items) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
