import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.access_log import (
    ACCESS_LOG_ENABLE_ATTR,
    record_api_access_log,
    set_request_start_perf,
)

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """
    配置应用中间件。

    Args:
        app (FastAPI): 应用实例。
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )

    @app.middleware("http")
    async def finalize_response(request: Request, call_next):
        """
        统一响应收尾，并在启用时落访问日志。

        Args:
            request (Request): 请求对象。
            call_next (Callable): 下游处理函数，负责执行后续中间件与路由。

        Returns:
            Response: 已附加 X-Process-Time 的响应对象。
        """
        # 单一起点，同时用于响应头耗时与访问日志耗时。
        start_time = time.perf_counter()
        set_request_start_perf(request, start_time)
        resp = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000)
        if getattr(request.state, ACCESS_LOG_ENABLE_ATTR, False):
            await record_api_access_log(request, elapsed_ms)
        resp.headers["X-Process-Time"] = f"{elapsed_ms / 1000:.6f}"
        return resp
