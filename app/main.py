from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware
from tortoise import Tortoise

from app.api import api_router
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import setup_middleware
from app.core.rate_limit import limiter
from app.core.settings import get_settings
from app.core import response


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    await Tortoise.init(
        db_url=settings.db_uri,
        modules={"models": ["app.models"]},
    )
    # 生成数据库表
    await Tortoise.generate_schemas(safe=True)
    yield
    await Tortoise.close_connections()

app = FastAPI(
    lifespan=lifespan,
    openapi_url=settings.openapi_url,
    docs_url=settings.docs_url if settings.enable_docs else None,
    redoc_url=settings.redoc_url if settings.enable_docs else None,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
setup_middleware(app)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health():
    return response.ok()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
