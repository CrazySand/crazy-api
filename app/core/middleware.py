import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.access_log import set_request_start_perf
from app.core import response
from app.core.settings import get_settings


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
    async def limit_request_body(request: Request, call_next):
        """
        超限则直接返回业务错误响应 不进入路由与 JSON 解析
        此处虽调用 respond_bad_request 但通常不会写入 ApiAccessLog
        原因是中间件短路返回时 endpoint 常为 None 会被访问日志条件过滤

        Args:
            request (Request): 请求对象
            call_next (Callable): 下游处理函数

        Returns:
            Response: 原样下游响应或 400 统一 JSON
        """
        limit = get_settings().max_request_body_bytes
        if limit <= 0:
            return await call_next(request)
        raw_cl = request.headers.get("content-length")
        if raw_cl is None:
            return await call_next(request)
        try:
            length = int(raw_cl.strip())
        except ValueError:
            return await call_next(request)
        if length < 0:
            return await response.respond_bad_request(request, msg="无效的 Content-Length")
        if length > limit:
            return await response.respond_bad_request(request, msg=f"请求体过大，最大限制为 {limit} 字节")
        return await call_next(request)

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
        resp = await call_next(request)
        elapsed = time.perf_counter() - start_time
        resp.headers["X-Process-Time"] = f"{elapsed:.6f}"
        return resp
