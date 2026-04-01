import logging
import time
from uuid import UUID

from fastapi import Request

from app.core.client_ip import get_client_ip
from app.core.response import ApiResponse
from app.core.security import TokenManager
from app.core.settings import get_settings
from app.models.api_access_log import ApiAccessLog


logger = logging.getLogger(__name__)

_REQUEST_START_PERF = "request_start_perf"
ACCESS_LOG_USER_ID_ATTR = "access_log_user_id"


def set_access_log_user_id(request: Request, user_id: UUID) -> None:
    """
    将业务 user_id 写入 request.state 供访问日志在无 Bearer 时使用

    Args:
        request (Request): 请求对象
        user_id (UUID): 业务用户 ID
    """
    setattr(request.state, ACCESS_LOG_USER_ID_ATTR, user_id)


def _resolve_access_log_user_id(request: Request) -> UUID | None:
    """
    解析访问日志中的用户 ID state 优先 否则 JWT

    Args:
        request (Request): 请求对象

    Returns:
        UUID | None: 可解析时返回 否则 None
    """
    raw = getattr(request.state, ACCESS_LOG_USER_ID_ATTR, None)
    if raw is not None:
        if isinstance(raw, UUID):
            return raw
        try:
            return UUID(str(raw))
        except (ValueError, TypeError):
            pass
    return _bearer_user_id(request)


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


def _is_whitelisted(path: str, whitelist: list[str]) -> bool:
    """
    判断路径是否命中访问日志白名单

    Args:
        path (str): 请求路径
        whitelist (list[str]): 白名单项

    Returns:
        bool: 为 True 时允许记录
    """
    for raw in whitelist:
        if _path_matches_prefix(path, raw):
            return True
    return False


def _is_excluded(path: str, excludes: list[str]) -> bool:
    """
    判断路径是否命中排除列表

    Args:
        path (str): 请求路径
        excludes (list[str]): 排除项

    Returns:
        bool: 为 True 时不写日志
    """
    for raw in excludes:
        if _path_matches_prefix(path, raw):
            return True
    return False


def _should_record(request: Request) -> bool:
    """
    判断本次请求是否应写入 ApiAccessLog

    Args:
        request (Request): 请求对象

    Returns:
        bool: 为 True 时写入
    """
    settings = get_settings()
    if not settings.enable_access_log:
        return False
    path = request.url.path
    whitelist = [
        p.strip()
        for p in settings.access_log_whitelist.split(",")
        if p.strip()
    ]
    if not _is_whitelisted(path, whitelist):
        return False
    excludes = [
        p.strip()
        for p in settings.access_log_exclude_paths.split(",")
        if p.strip()
    ]
    if _is_excluded(path, excludes):
        return False
    if request.scope.get("endpoint") is None:
        return False
    return True


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


def _duration_ms(request: Request) -> int:
    """
    根据 request.state 中的起点计算耗时毫秒

    Args:
        request (Request): 请求对象

    Returns:
        int: 耗时毫秒 无起点时为 0
    """
    start = getattr(request.state, _REQUEST_START_PERF, None)
    if start is None:
        return 0
    return int(round((time.perf_counter() - start) * 1000))


async def record_api_access_log(request: Request, body: ApiResponse) -> None:
    """
    将统一 ApiResponse 写入 ApiAccessLog 含 code 与 msg 不读响应体

    Args:
        request (Request): 请求对象
        body (ApiResponse): 统一响应体
    """
    if not _should_record(request):
        return
    path = request.url.path
    api_msg = body.msg[:512] if body.msg else None
    try:
        await ApiAccessLog.create(
            user_id=_resolve_access_log_user_id(request),
            method=request.method,
            path=path,
            api_code=int(body.code),
            api_msg=api_msg,
            duration_ms=_duration_ms(request),
            client_ip=get_client_ip(request),
        )
    except Exception:
        logger.exception("写入接口访问日志失败")


def set_request_start_perf(request: Request) -> None:
    """
    在请求进入时写入 perf 起点供访问日志计算耗时

    Args:
        request (Request): 请求对象
    """
    setattr(request.state, _REQUEST_START_PERF, time.perf_counter())
