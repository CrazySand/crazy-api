import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.access_log import (
    ACCESS_LOG_ENABLE_ATTR,
    record_api_access_log,
    set_request_start_perf,
    update_api_access_log_duration,
)
from app.core.response import ApiResponse

logger = logging.getLogger(__name__)


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
    async def finalize_response(request: Request, call_next):
        """
        统一响应收尾并在启用时落访问日志

        Args:
            request (Request): 请求对象
            call_next (Callable): 下游处理函数 负责执行后续中间件与路由

        Returns:
            Response: 已附加 X-Process-Time 的响应对象
        """
        # 单一起点 同时用于响应头耗时与访问日志耗时
        start_time = time.perf_counter()
        set_request_start_perf(request, start_time)
        elapsed_ms: int | None = None
        resp = await call_next(request)
        if getattr(request.state, ACCESS_LOG_ENABLE_ATTR, False):
            # 优先读取已物化的 body 无 body 时尝试消费 body_iterator
            raw = getattr(resp, "body", None)
            if raw is None:
                iterator = getattr(resp, "body_iterator", None)
                if iterator is not None:
                    parts: list[bytes] = []
                    async for chunk in iterator:
                        parts.append(chunk)
                    joined = b"".join(parts)
                    resp = StarletteResponse(
                        content=joined,
                        status_code=resp.status_code,
                        headers=dict(resp.headers),
                        media_type=resp.media_type,
                        background=getattr(resp, "background", None),
                    )
                    raw = joined
            if raw is not None:
                # 仅解析统一 ApiResponse 结构 解析失败仅告警不影响主请求
                data = raw if isinstance(raw, bytes) else bytes(raw)
                try:
                    payload = ApiResponse.model_validate_json(data)
                    record = await record_api_access_log(request, payload)
                    if record is not None:
                        elapsed_ms = int(round((time.perf_counter() - start_time) * 1000))
                        await update_api_access_log_duration(record.id, elapsed_ms)
                except Exception:
                    logger.warning(
                        f"访问日志解析响应体失败 path={request.url.path} "
                        f"status={getattr(resp, 'status_code', 'unknown')} "
                        f"content_type={resp.headers.get('content-type')}",
                        exc_info=True,
                    )
        if elapsed_ms is None:
            elapsed_ms = int(round((time.perf_counter() - start_time) * 1000))
        resp.headers["X-Process-Time"] = f"{elapsed_ms / 1000:.6f}"
        return resp
