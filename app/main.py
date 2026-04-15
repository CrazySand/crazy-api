from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware
from tortoise import Tortoise

from app.api import api_router
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import setup_middleware
from app.core.rate_limit import limiter
from app.core.response import ApiCode, build_response
from app.core.settings import get_settings

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

from fastapi import Depends
from app.core.deps import enable_access_log
@app.get("/health", dependencies=[Depends(enable_access_log)])
async def health():
    return build_response(ApiCode.OK, msg="服务正常")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
