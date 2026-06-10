import logging
import time
from uuid import UUID

from fastapi import Request

from app.core.client_ip import get_client_ip
from app.core.security import TokenManager
from app.models.api_access_log import ApiAccessLog

logger = logging.getLogger(__name__)

_REQUEST_START_PERF = "request_start_perf"
ACCESS_LOG_ENABLE_ATTR = "enable_access_log"
ACCESS_LOG_USER_ID_ATTR = "access_log_user_id"
ACCESS_LOG_API_CODE_ATTR = "access_log_api_code"
ACCESS_LOG_API_MSG_ATTR = "access_log_api_msg"


def set_access_log_user_id(request: Request, user_id: UUID) -> None:
    """
    将业务 user_id 写入 request.state，供访问日志在无 Bearer 时使用。

    Args:
        request (Request): 请求对象。
        user_id (UUID): 业务用户 ID。
    """
    setattr(request.state, ACCESS_LOG_USER_ID_ATTR, user_id)


def set_access_log_result(request: Request, api_code: int, api_msg: str | None) -> None:
    """
    将业务响应码与消息写入 request.state，供访问日志使用。

    Args:
        request (Request): 请求对象。
        api_code (int): 业务响应码。
        api_msg (str | None): 业务响应消息。
    """
    setattr(request.state, ACCESS_LOG_API_CODE_ATTR, api_code)
    setattr(request.state, ACCESS_LOG_API_MSG_ATTR, api_msg[:512] if api_msg else None)


def _resolve_access_log_result(request: Request) -> tuple[int, str | None]:
    """
    解析访问日志中的业务响应码与消息。

    Args:
        request (Request): 请求对象。

    Returns:
        tuple[int, str | None]: 业务响应码与消息。
    """
    raw_code: int = getattr(request.state, ACCESS_LOG_API_CODE_ATTR, None)
    api_msg = getattr(request.state, ACCESS_LOG_API_MSG_ATTR, None)
    return raw_code, api_msg


def _resolve_access_log_user_id(request: Request) -> UUID | None:
    """
    解析访问日志中的用户 ID，state 优先，否则回退 JWT。

    Args:
        request (Request): 请求对象。

    Returns:
        UUID | None: 可解析时返回用户 ID，否则为 None。
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


def _should_record(request: Request) -> bool:
    """
    判断本次请求是否应写入 ApiAccessLog。

    Args:
        request (Request): 请求对象。

    Returns:
        bool: 为 True 时写入。
    """
    if not getattr(request.state, ACCESS_LOG_ENABLE_ATTR, False):
        return False
    return True


def _bearer_user_id(request: Request) -> UUID | None:
    """
    从 Authorization Bearer JWT 中解析业务 user_id。

    Args:
        request (Request): 请求对象。

    Returns:
        UUID | None: JWT 合法且含 sub 时返回用户 ID，否则为 None。
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


async def record_api_access_log(request: Request, duration_ms: int) -> ApiAccessLog | None:
    """
    将当前请求写入 ApiAccessLog 并返回记录对象。

    Args:
        request (Request): 请求对象。
        duration_ms (int): 全链路耗时毫秒。

    Returns:
        ApiAccessLog | None: 写入成功返回记录，否则为 None。
    """
    if not _should_record(request):
        return None
    api_code, api_msg = _resolve_access_log_result(request)
    path = request.url.path
    try:
        return await ApiAccessLog.create(
            user_id=_resolve_access_log_user_id(request),
            method=request.method,
            path=path,
            api_code=api_code,
            api_msg=api_msg,
            duration_ms=duration_ms,
            client_ip=get_client_ip(request),
        )
    except Exception:
        logger.exception("写入接口访问日志失败")
        return None


def set_request_start_perf(request: Request, start: float | None = None) -> None:
    """
    在请求进入时写入 perf 起点，供访问日志计算耗时。

    Args:
        request (Request): 请求对象。
        start (float | None): 调用方传入的 perf 起点，缺省时取当前时刻。
    """
    setattr(request.state, _REQUEST_START_PERF, time.perf_counter() if start is None else start)
