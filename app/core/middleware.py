import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.access_log import set_request_start_perf


def setup_middleware(app: FastAPI) -> None:
    """
    配置应用中间件

    Args:
        app (FastAPI): 应用实例
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
    async def add_process_time_header(request: Request, call_next):
        """
        写入 X-Process-Time 与访问日志耗时起点

        Args:
            request (Request): 请求对象
            call_next (Callable): 下游处理函数

        Returns:
            Response: 带耗时头的响应对象
        """
        set_request_start_perf(request)
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        return response
