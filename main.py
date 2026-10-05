"""Fashion Trend Service - 全球时尚趋势采集与分析服务

FastAPI + SQLAlchemy + SQLite
负责采集、聚合、缓存、排序全球时尚趋势数据，
并提供AI搭配灵感生成能力。

合规底线：
- 不绕过登录、验证码、付费墙
- 遵守robots.txt和平台ToS
- 只存元数据、摘要、缩略图URL、原文链接
- 商业使用前必须获得授权
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, SessionLocal
from services.trend_service import trend_service
from routers import trends, creators, magazines, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库和默认数据源"""
    # 初始化数据库表
    init_db()

    # 初始化默认RSS数据源
    db = SessionLocal()
    try:
        trend_service.init_default_sources(db)
    finally:
        db.close()

    # 启动定时采集任务（后台）
    scheduler_task = asyncio.create_task(_periodic_refresh())

    yield

    # 关闭时取消定时任务
    scheduler_task.cancel()


async def _periodic_refresh():
    """定时采集任务"""
    while True:
        try:
            await asyncio.sleep(settings.REFRESH_INTERVAL_MINUTES * 60)
            await trend_service.refresh_trends()
        except asyncio.CancelledError:
            break
        except Exception:
            # 采集失败不影响服务运行
            await asyncio.sleep(60)


app = FastAPI(
    title="Fashion Trend Service",
    description="全球时尚趋势采集与分析服务 - 为电子衣柜提供实时穿搭灵感",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trends.router)
app.include_router(creators.router)
app.include_router(magazines.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    """服务健康检查"""
    return {
        "service": "Fashion Trend Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "trends": "/api/trends/outfits",
            "creators": "/api/creators",
            "magazines": "/api/magazines/latest",
            "ai_styling": "/api/ai/styling-inspiration",
            "refresh": "/api/trends/refresh (POST)",
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
