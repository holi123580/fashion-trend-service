"""配置管理 - 从环境变量读取"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./fashion_trends.db"

    # 服务
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "*"

    # Apify (可选)
    APIFY_TOKEN: Optional[str] = None

    # 采集配置
    REFRESH_INTERVAL_MINUTES: int = 60
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    USER_AGENT: str = "SmartWardrobe-TrendBot/1.0 (contact: admin@example.com)"

    # 缓存
    CACHE_TTL_SECONDS: int = 300  # 5分钟

    # AI (可选，用于搭配灵感生成)
    AI_API_KEY: Optional[str] = None
    AI_API_BASE: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"


settings = Settings()
