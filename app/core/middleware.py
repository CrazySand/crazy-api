import json
import logging
import time
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.core.client_ip import get_client_ip
from app.core.security import TokenManager
from app.core.settings import get_settings
from app.models.api_access_log import ApiAccessLog


logger = logging.getLogger(__name__)

# 内层耗时中间件写入 供外层访问日志读取 与 X-Process-Time 同源
_REQUEST_STATE_PROCESS_TIME_SEC = "process_time_seconds"


def _path_matches_prefix(path: str, prefix: str) -> bool:
    """
    判断路径是否等于某前缀或其子路径

    Args:
        path (str): 请求路径
        prefix (str): 前缀字符串

    Returns:
        bool: 匹配时为 True
    """
    p = prefix.strip()
    if not p:
        return False
    return path == p or path.startswith(p + "/")


def _is_access_log_whitelisted(path: str, whitelist: list[str]) -> bool:
    """
    判断路径是否命中访问日志白名单

    Args:
        path (str): 请求路径
        whitelist (list[str]): 白名单项 与 path 相等或为其子路径前缀则允许记录

    Returns:
        bool: 为 True 时允许写入访问日志
    """
    for raw in whitelist:
        if _path_matches_prefix(path, raw):
            return True
    return False


def _is_access_log_excluded(path: str, excludes: list[str]) -> bool:
    """
    判断路径是否命中访问日志排除列表 命中则不写入 ApiAccessLog

    Args:
        path (str): 请求路径
        excludes (list[str]): 排除项列表

    Returns:
        bool: 为 True 时不写访问日志
    """
    for raw in excludes:
        if _path_matches_prefix(path, raw):
            return True
    return False


def _should_log_access(
    request: Request,
    response: Response,
    whitelist: list[str],
    excludes: list[str],
) -> bool:
    """
    判断是否应写入接口访问日志

    Args:
        request (Request): 请求对象
        response (Response): 响应对象
        whitelist (list[str]): 允许记录的路径白名单
        excludes (list[str]): 命中则不写入访问日志的路径列表

    Returns:
        bool: 为 True 时写入日志
    """
    path = request.url.path
    if not _is_access_log_whitelisted(path, whitelist):
        return False
    if _is_access_log_excluded(path, excludes):
        return False
    if request.scope.get("endpoint") is None:
        return False
    if response.status_code != 200:
        return False
    return True


async def _read_response_bytes(response: Response) -> bytes | None:
    """
    读取 Starlette 响应体字节 无 body() 时消费 body_iterator 与业务是否流式无关

    Args:
        response (Response): 下游响应

    Returns:
        bytes | None: 成功时为完整 body 失败时为 None
    """
    body_m = getattr(response, "body", None)
    if callable(body_m):
        try:
            return await body_m()
        except Exception:
            logger.exception("读取响应体失败")
            return None
    it = getattr(response, "body_iterator", None)
    if it is not None:
        try:
            chunks: list[bytes] = []
            async for chunk in it:
                chunks.append(chunk)
            return b"".join(chunks)
        except Exception:
            logger.exception("读取响应体失败")
            return None
    return None


async def _response_json_for_access_log(
    response: Response,
) -> tuple[Response, int | None, str | None]:
    """
    读取 JSON 响应体提取 code 与 msg 并返回重建后的 Response

    Args:
        response (Response): 下游响应

    Returns:
        tuple[Response, int | None, str | None]: 重建后的响应 业务码 截断后的 msg
    """
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return response, None, None

    body = await _read_response_bytes(response)
    if body is None:
        return response, None, None

    rebuilt = Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )

    api_code: int | None = None
    api_msg: str | None = None
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return rebuilt, None, None

    if isinstance(data, dict):
        raw_code = data.get("code")
        if raw_code is not None:
            try:
                api_code = int(raw_code)
            except (TypeError, ValueError):
                pass
        raw_msg = data.get("msg")
        if raw_msg is not None:
            api_msg = str(raw_msg)[:512]

    return rebuilt, api_code, api_msg


def _bearer_user_id(request: Request) -> UUID | None:
    """
    从 Authorization Bearer JWT 中解析业务 user_id

    Args:
        request (Request): 请求对象

    Returns:
        UUID | None: JWT 合法且含 sub 时返回 否则 None
    """
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    payload = TokenManager.decode(token)
    if payload is None:
        return None
    try:
        return UUID(str(payload["user_id"]))
    except (KeyError, ValueError, TypeError):
        return None


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
        写入 X-Process-Time 响应头并在 state 保留秒级耗时

        Args:
            request (Request): 请求对象
            call_next (Callable): 下游处理函数

        Returns:
            Response: 带耗时头的响应对象
        """
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        setattr(request.state, _REQUEST_STATE_PROCESS_TIME_SEC, elapsed)
        return response

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        """
        按规则将接口访问写入 ApiAccessLog

        Args:
            request (Request): 请求对象
            call_next (Callable): 下游处理函数

        Returns:
            Response: 下游响应 JSON 时会读取整段 body 并可能重建
        """
        response = await call_next(request)
        settings = get_settings()
        if not settings.enable_access_log:
            return response

        path = request.url.path
        whitelist = [
            p.strip()
            for p in settings.access_log_whitelist.split(",")
            if p.strip()
        ]
        excludes = [
            p.strip()
            for p in settings.access_log_exclude_paths.split(",")
            if p.strip()
        ]
        if not _should_log_access(request, response, whitelist, excludes):
            return response

        response, api_code, api_msg = await _response_json_for_access_log(
            response)

        elapsed_sec = getattr(
            request.state, _REQUEST_STATE_PROCESS_TIME_SEC, None)
        if elapsed_sec is None:
            elapsed_sec = 0.0
        duration_ms = int(round(elapsed_sec * 1000))
        try:
            await ApiAccessLog.create(
                user_id=_bearer_user_id(request),
                method=request.method,
                path=path,
                api_code=api_code,
                api_msg=api_msg,
                duration_ms=duration_ms,
                client_ip=get_client_ip(request),
            )
        except Exception:
            logger.exception("写入接口访问日志失败")

        return response
