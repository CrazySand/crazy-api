import logging
import time
from uuid import UUID

from fastapi import Request

from app.core.client_ip import get_client_ip
from app.core.response import ApiResponse
from app.core.security import TokenManager
from app.models.api_access_log import ApiAccessLog

logger = logging.getLogger(__name__)

_REQUEST_START_PERF = "request_start_perf"
ACCESS_LOG_USER_ID_ATTR = "access_log_user_id"
ACCESS_LOG_ENABLE_ATTR = "enable_access_log"


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


def _should_record(request: Request) -> bool:
    """
    判断本次请求是否应写入 ApiAccessLog

    Args:
        request (Request): 请求对象

    Returns:
        bool: 为 True 时写入
    """
    if not getattr(request.state, ACCESS_LOG_ENABLE_ATTR, False):
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


async def record_api_access_log(request: Request, body: ApiResponse) -> ApiAccessLog | None:
    """
    将统一 ApiResponse 写入 ApiAccessLog 并返回记录对象

    Args:
        request (Request): 请求对象
        body (ApiResponse): 中间件从响应 body 解析得到的统一响应体

    Returns:
        ApiAccessLog | None: 写入成功返回记录 否则 None
    """
    if not _should_record(request):
        return None
    path = request.url.path
    api_msg = body.msg[:512] if body.msg else None
    try:
        return await ApiAccessLog.create(
            user_id=_resolve_access_log_user_id(request),
            method=request.method,
            path=path,
            api_code=int(body.code),
            api_msg=api_msg,
            duration_ms=0,
            client_ip=get_client_ip(request),
        )
    except Exception:
        logger.exception("写入接口访问日志失败")
        return None


async def update_api_access_log_duration(record_id: int, duration_ms: int) -> None:
    """
    按主键更新 ApiAccessLog 耗时毫秒

    Args:
        record_id (int): 日志主键
        duration_ms (int): 全链路耗时毫秒
    """
    try:
        await ApiAccessLog.filter(id=record_id).update(duration_ms=duration_ms)
    except Exception:
        logger.exception("回写接口访问日志耗时失败")


def set_request_start_perf(request: Request, start: float | None = None) -> None:
    """
    在请求进入时写入 perf 起点供访问日志计算耗时

    Args:
        request (Request): 请求对象
        start (float | None): 调用方传入的 perf 起点 缺省时取当前时刻
    """
    setattr(request.state, _REQUEST_START_PERF, time.perf_counter() if start is None else start)
