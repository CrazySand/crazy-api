from starlette.requests import Request

from app.core.settings import get_settings


def get_client_ip(request: Request) -> str | None:
    """
    按配置解析客户端 IP 供日志与限流分桶

    Args:
        request (Request): 请求对象

    Returns:
        str | None: 客户端 IP 无则 None
    """
    settings = get_settings()
    src = settings.client_ip_source

    if src == "direct":
        return request.client.host if request.client else None

    if src == "x_real_ip":
        raw = request.headers.get("x-real-ip")
        if raw:
            return raw.strip()
        return None

    raw = request.headers.get("x-real-ip")
    if raw:
        return raw.strip()
    if request.client:
        return request.client.host
    return None


def get_client_ip_for_rate_limit(request: Request) -> str:
    """
    供 SlowAPI key_func 使用 保证返回非空字符串

    Args:
        request (Request): 请求对象

    Returns:
        str: 用作限流分桶的 IP 字符串
    """
    ip = get_client_ip(request)
    if ip:
        return ip
    return "127.0.0.1"
