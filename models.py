"""SQLAlchemy 数据库模型 - 7张表"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, JSON, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Source(Base):
    """数据来源表"""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)  # 来源名称：Vogue, Hypebeast...
    type = Column(String(50), nullable=False)  # rss / apify / api / scraper
    url = Column(String(500), nullable=False)  # RSS URL 或 API endpoint
    region = Column(String(50), default="global")  # global / jp / kr / us / eu / cn
    language = Column(String(20), default="en")
    enabled = Column(Boolean, default=True)
    last_fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="source")
    magazine_articles = relationship("MagazineArticle", back_populates="source")


class Creator(Base):
    """时尚博主/创作者表"""
    __tablename__ = "creators"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)  # youtube / pinterest / tiktok / wear / musinsa / instagram
    username = Column(String(200), nullable=False, index=True)
    display_name = Column(String(200), nullable=True)
    profile_url = Column(String(500), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    followers = Column(Integer, default=0)  # 粉丝数
    region = Column(String(50), default="global")
    style_tags = Column(JSON, default=list)  # 风格标签列表
    bio = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="creator")


class Post(Base):
    """帖子/内容表"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.id"), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    platform = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)  # 正文摘要（不存完整版权文章）
    image_urls = Column(JSON, default=list)  # 图片URL列表（只存URL，不存原图）
    original_url = Column(String(500), nullable=False, index=True)  # 原文链接
    likes = Column(Integer, default=0)
    favorites = Column(Integer, default=0)  # 收藏数
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True, index=True)
    region = Column(String(50), default="global")
    style_tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("Creator", back_populates="posts")
    source = relationship("Source", back_populates="posts")
    outfits = relationship("Outfit", back_populates="post")


class Outfit(Base):
    """搭配方案表"""
    __tablename__ = "outfits"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    outfit_image_url = Column(String(500), nullable=True)  # 搭配图片URL
    title = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    brands = Column(JSON, default=list)  # 品牌列表
    style_tags = Column(JSON, default=list)  # 风格标签
    season = Column(String(20), nullable=True)  # spring/summer/autumn/winter/all
    region = Column(String(50), default="global")
    likes = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="outfits")
    items = relationship("OutfitItem", back_populates="outfit", cascade="all, delete-orphan")


class OutfitItem(Base):
    """搭配单品表"""
    __tablename__ = "outfit_items"

    id = Column(Integer, primary_key=True, index=True)
    outfit_id = Column(Integer, ForeignKey("outfits.id"), nullable=False)
    name = Column(String(200), nullable=False)  # 单品名称
    brand = Column(String(200), nullable=True)
    category = Column(String(50), nullable=True)  # outer/top/bottom/shoes/accessory
    color = Column(String(50), nullable=True)
    image_url = Column(String(500), nullable=True)
    purchase_url = Column(String(500), nullable=True)  # 购买链接
    price = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    outfit = relationship("Outfit", back_populates="items")


class TrendSignal(Base):
    """趋势信号表 - 热度计算结果"""
    __tablename__ = "trend_signals"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    region = Column(String(50), default="global", index=True)
    style = Column(String(100), nullable=True, index=True)
    keyword = Column(String(200), nullable=True, index=True)
    heat_score = Column(Float, default=0.0)  # 综合热度分 0-100
    followers_count = Column(Integer, default=0)  # 相关粉丝量
    likes_count = Column(Integer, default=0)  # 相关点赞量
    sales_count = Column(Integer, default=0)  # 相关销售量/排名
    post_count = Column(Integer, default=0)  # 相关帖子数
    calculated_at = Column(DateTime, default=datetime.utcnow, index=True)
    time_window_days = Column(Integer, default=7)
    created_at = Column(DateTime, default=datetime.utcnow)


class MagazineArticle(Base):
    """杂志文章表"""
    __tablename__ = "magazine_articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    magazine_name = Column(String(200), nullable=False, index=True)  # 杂志名
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)  # 摘要（不存完整文章）
    cover_image_url = Column(String(500), nullable=True)
    original_url = Column(String(500), nullable=False, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    tags = Column(JSON, default=list)
    author = Column(String(200), nullable=True)
    region = Column(String(50), default="global")
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="magazine_articles")
