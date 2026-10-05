"""趋势服务 - 采集、聚合、缓存、排序、热度计算"""
import asyncio
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import SessionLocal
from models import Source, Creator, Post, Outfit, OutfitItem, TrendSignal, MagazineArticle
from adapters import RSSAdapter, ApifyAdapter
from adapters.rss import PRESET_RSS_FEEDS
from config import settings


class TrendService:
    """趋势服务核心类"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Any, datetime]] = {}

    # ===== 缓存 =====
    def _get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            data, expire_at = self._cache[key]
            if datetime.utcnow() < expire_at:
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any, ttl: int = None):
        """设置缓存"""
        ttl = ttl or settings.CACHE_TTL_SECONDS
        self._cache[key] = (data, datetime.utcnow() + timedelta(seconds=ttl))

    def _make_cache_key(self, prefix: str, **kwargs) -> str:
        """生成缓存key"""
        raw = f"{prefix}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()

    # ===== 初始化数据源 =====
    def init_default_sources(self, db: Session):
        """初始化默认数据源（RSS源）"""
        existing = {s.name for s in db.query(Source).all()}

        for feed_key, feed_config in PRESET_RSS_FEEDS.items():
            if feed_config["name"] not in existing:
                source = Source(
                    name=feed_config["name"],
                    type="rss",
                    url=feed_config["url"],
                    region=feed_config["region"],
                    language=feed_config["language"],
                    enabled=True,
                )
                db.add(source)

        db.commit()

    # ===== 采集 =====
    async def refresh_trends(self, source_names: Optional[List[str]] = None, force: bool = False) -> Dict[str, Any]:
        """手动触发采集

        Args:
            source_names: 指定来源名称，不传则采集所有启用的来源
            force: 是否强制刷新（忽略last_fetched_at）

        Returns:
            采集结果统计
        """
        db = SessionLocal()
        try:
            # 查询要采集的来源
            query = db.query(Source).filter(Source.enabled == True)
            if source_names:
                query = query.filter(Source.name.in_(source_names))
            sources = query.all()

            if not sources:
                return {"success": False, "message": "No enabled sources found", "fetched": 0}

            # 并发采集
            tasks = []
            for source in sources:
                # 检查是否需要刷新（非force模式下，距离上次采集不足10分钟跳过）
                if not force and source.last_fetched_at:
                    if (datetime.utcnow() - source.last_fetched_at).total_seconds() < 600:
                        continue

                if source.type == "rss":
                    # 找到对应的feed_key
                    feed_key = None
                    for key, config in PRESET_RSS_FEEDS.items():
                        if config["name"] == source.name:
                            feed_key = key
                            break
                    if feed_key:
                        adapter = RSSAdapter(feed_key, custom_url=source.url)
                        tasks.append(self._fetch_and_save(db, adapter, source))
                elif source.type == "apify":
                    # Apify需要token
                    if settings.APIFY_TOKEN:
                        adapter = ApifyAdapter(
                            actor_key=source.name.lower().replace(" ", "_"),
                            api_token=settings.APIFY_TOKEN,
                        )
                        tasks.append(self._fetch_and_save(db, adapter, source))

            if not tasks:
                return {"success": True, "message": "All sources recently fetched, use force=true to refresh", "fetched": 0}

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计结果
            stats = {"posts": 0, "creators": 0, "outfits": 0, "magazine_articles": 0, "errors": []}
            for result in results:
                if isinstance(result, Exception):
                    stats["errors"].append(str(result))
                elif result:
                    stats["posts"] += result.get("posts", 0)
                    stats["creators"] += result.get("creators", 0)
                    stats["outfits"] += result.get("outfits", 0)
                    stats["magazine_articles"] += result.get("magazine_articles", 0)
                    if result.get("error"):
                        stats["errors"].append(result["error"])

            # 计算趋势信号
            self._calculate_trend_signals(db)

            # 清除相关缓存
            self._cache.clear()

            return {
                "success": True,
                "message": f"Fetched {len(tasks)} sources",
                "sources_fetched": len(tasks),
                **stats,
            }
        finally:
            db.close()

    async def _fetch_and_save(self, db: Session, adapter, source: Source) -> Dict[str, Any]:
        """执行采集并保存到数据库"""
        try:
            result = await adapter.fetch()

            # 更新来源最后采集时间
            source.last_fetched_at = datetime.utcnow()

            if result.error:
                return {"error": f"{source.name}: {result.error}", "posts": 0}

            saved = {"posts": 0, "creators": 0, "outfits": 0, "magazine_articles": 0}

            # 保存创作者
            creator_map = {}  # username -> creator_id
            for creator_data in result.creators:
                existing = db.query(Creator).filter(
                    Creator.platform == creator_data["platform"],
                    Creator.username == creator_data["username"],
                ).first()
                if existing:
                    existing.followers = creator_data.get("followers", existing.followers)
                    existing.last_updated = datetime.utcnow()
                    creator_map[creator_data["username"]] = existing.id
                else:
                    creator = Creator(**creator_data)
                    db.add(creator)
                    db.flush()
                    creator_map[creator_data["username"]] = creator.id
                saved["creators"] += 1

            # 保存帖子（去重：按original_url）
            for post_data in result.posts:
                if not post_data.get("original_url"):
                    continue
                existing = db.query(Post).filter(Post.original_url == post_data["original_url"]).first()
                if existing:
                    # 更新互动数据
                    existing.likes = post_data.get("likes", existing.likes)
                    existing.favorites = post_data.get("favorites", existing.favorites)
                    existing.comments = post_data.get("comments", existing.comments)
                    continue

                post = Post(
                    source_id=source.id,
                    platform=post_data["platform"],
                    title=post_data.get("title"),
                    summary=post_data.get("summary"),
                    image_urls=post_data.get("image_urls", []),
                    original_url=post_data["original_url"],
                    likes=post_data.get("likes", 0),
                    favorites=post_data.get("favorites", 0),
                    comments=post_data.get("comments", 0),
                    shares=post_data.get("shares", 0),
                    published_at=post_data.get("published_at"),
                    region=post_data.get("region", "global"),
                    style_tags=post_data.get("style_tags", []),
                )
                db.add(post)
                saved["posts"] += 1

            # 保存搭配
            for outfit_data in result.outfits:
                items_data = outfit_data.pop("items", [])
                outfit = Outfit(source_id=source.id, **outfit_data)
                db.add(outfit)
                db.flush()
                for item_data in items_data:
                    item = OutfitItem(outfit_id=outfit.id, **item_data)
                    db.add(item)
                saved["outfits"] += 1

            # 保存杂志文章
            for article_data in result.magazine_articles:
                if not article_data.get("original_url"):
                    continue
                existing = db.query(MagazineArticle).filter(
                    MagazineArticle.original_url == article_data["original_url"]
                ).first()
                if existing:
                    continue
                article = MagazineArticle(source_id=source.id, **article_data)
                db.add(article)
                saved["magazine_articles"] += 1

            db.commit()
            return saved

        except Exception as e:
            db.rollback()
            return {"error": f"{source.name}: {str(e)}", "posts": 0}

    # ===== 查询：搭配图 =====
    def get_outfits(
        self,
        region: str = "global",
        sort_by: str = "likes",
        days: int = 7,
        style: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Outfit], int]:
        """获取搭配列表，支持排序和筛选

        Args:
            region: 地区筛选
            sort_by: 排序方式 followers/likes/sales/heat
            days: 时间窗口（天）
            style: 风格标签筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            (搭配列表, 总数)
        """
        cache_key = self._make_cache_key("outfits", region=region, sort_by=sort_by, days=days, style=style, limit=limit, offset=offset)
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        db = SessionLocal()
        try:
            query = db.query(Outfit)

            # 地区筛选
            if region and region != "global":
                query = query.filter(Outfit.region == region)

            # 时间窗口
            if days > 0:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(Outfit.published_at >= cutoff)

            # 风格筛选
            if style:
                query = query.filter(Outfit.style_tags.contains([style]))

            # 总数
            total = query.count()

            # 排序
            if sort_by == "followers":
                # 按粉丝量排序需要关联creator，这里用post的creator粉丝量
                query = query.outerjoin(Post, Outfit.post_id == Post.id).outerjoin(Creator, Post.creator_id == Creator.id)
                query = query.order_by(desc(Creator.followers), desc(Outfit.likes))
            elif sort_by == "likes":
                query = query.order_by(desc(Outfit.likes), desc(Outfit.published_at))
            elif sort_by == "sales":
                # 销售量排序：暂时用likes作为代理（搭配没有直接销量数据）
                query = query.order_by(desc(Outfit.likes), desc(Outfit.published_at))
            elif sort_by == "heat":
                # 综合热度排序
                query = query.order_by(desc(Outfit.likes), desc(Outfit.published_at))
            else:
                query = query.order_by(desc(Outfit.published_at))

            outfits = query.offset(offset).limit(limit).all()
            result = (outfits, total)
            self._set_cache(cache_key, result)
            return result
        finally:
            db.close()

    # ===== 查询：博主 =====
    def get_creators(
        self,
        platform: Optional[str] = None,
        sort_by: str = "followers",
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Creator], int]:
        """获取创作者/博主列表"""
        cache_key = self._make_cache_key("creators", platform=platform, sort_by=sort_by, limit=limit, offset=offset)
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        db = SessionLocal()
        try:
            query = db.query(Creator)

            if platform:
                query = query.filter(Creator.platform == platform)

            total = query.count()

            if sort_by == "followers":
                query = query.order_by(desc(Creator.followers))
            elif sort_by == "likes":
                # 按总点赞量排序（需要关联post）
                query = query.outerjoin(Post, Creator.id == Post.creator_id).group_by(Creator.id).order_by(desc(func.coalesce(func.sum(Post.likes), 0)))
            else:
                query = query.order_by(desc(Creator.followers))

            creators = query.offset(offset).limit(limit).all()
            result = (creators, total)
            self._set_cache(cache_key, result)
            return result
        finally:
            db.close()

    # ===== 查询：杂志文章 =====
    def get_magazine_articles(
        self,
        source: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[MagazineArticle], int]:
        """获取最新杂志文章"""
        cache_key = self._make_cache_key("magazines", source=source, limit=limit, offset=offset)
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        db = SessionLocal()
        try:
            query = db.query(MagazineArticle)

            if source:
                query = query.filter(MagazineArticle.magazine_name == source)

            total = query.count()
            query = query.order_by(desc(MagazineArticle.published_at))
            articles = query.offset(offset).limit(limit).all()
            result = (articles, total)
            self._set_cache(cache_key, result)
            return result
        finally:
            db.close()

    # ===== 趋势信号计算 =====
    def _calculate_trend_signals(self, db: Session):
        """计算趋势信号 - 综合热度算法

        综合热度 = 0.4*点赞归一化 + 0.3*粉丝归一化 + 0.2*销量归一化 + 0.1*时间新鲜度
        """
        # 获取最近7天的帖子数据
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent_posts = db.query(Post).filter(Post.published_at >= cutoff).all()

        if not recent_posts:
            return

        # 计算最大值用于归一化
        max_likes = max((p.likes for p in recent_posts), default=1) or 1
        max_comments = max((p.comments for p in recent_posts), default=1) or 1

        # 按地区和风格分组计算
        from collections import defaultdict
        region_style_stats = defaultdict(lambda: {"likes": 0, "comments": 0, "posts": 0, "creators": set()})

        for post in recent_posts:
            key = (post.region, tuple(post.style_tags[:3]) if post.style_tags else ("general",))
            region_style_stats[key]["likes"] += post.likes
            region_style_stats[key]["comments"] += post.comments
            region_style_stats[key]["posts"] += 1
            if post.creator_id:
                region_style_stats[key]["creators"].add(post.creator_id)

        # 计算并保存趋势信号
        for (region, styles), stats in region_style_stats.items():
            # 归一化
            likes_norm = min(stats["likes"] / max_likes, 1.0) if max_likes > 0 else 0
            comments_norm = min(stats["comments"] / max_comments, 1.0) if max_comments > 0 else 0
            creator_count = len(stats["creators"])
            # 时间新鲜度：最近的帖子权重更高（简化为1.0，因为都是7天内）
            freshness = 1.0

            # 综合热度 = 0.4*点赞 + 0.3*评论(代理粉丝互动) + 0.2*创作者数 + 0.1*新鲜度
            heat_score = (
                0.4 * likes_norm * 100
                + 0.3 * comments_norm * 100
                + 0.2 * min(creator_count / 10, 1.0) * 100
                + 0.1 * freshness * 100
            )

            signal = TrendSignal(
                region=region,
                style=styles[0] if styles else None,
                keyword=styles[0] if styles else None,
                heat_score=round(heat_score, 2),
                followers_count=creator_count,
                likes_count=stats["likes"],
                sales_count=0,  # 销量数据需要电商平台接入
                post_count=stats["posts"],
                time_window_days=7,
            )
            db.add(signal)

        db.commit()

    def get_trend_signals(self, region: str = "global", limit: int = 20) -> List[TrendSignal]:
        """获取趋势信号"""
        db = SessionLocal()
        try:
            query = db.query(TrendSignal)
            if region and region != "global":
                query = query.filter(TrendSignal.region == region)
            query = query.order_by(desc(TrendSignal.heat_score)).limit(limit)
            return query.all()
        finally:
            db.close()


# 全局单例
trend_service = TrendService()
