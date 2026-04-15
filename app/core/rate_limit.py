from slowapi import Limiter
from starlette.requests import Request

from app.core.client_ip import get_client_ip_for_rate_limit
from app.core.security import TokenManager

LOGIN_PER_IP = "10/minute"        # 登录：单 IP 每分钟最多 10 次
REGISTER_PER_IP = "10/minute"     # 注册：单 IP 每分钟最多 10 次
USER_ME_PER_USER = "60/minute"    # 获取个人信息：单用户每分钟最多 60 次

limiter = Limiter(
    key_func=get_client_ip_for_rate_limit,
    # 全局默认不限流，只在挂了 @limiter.limit(...) 的路由上生效
    default_limits=[],
)


def get_user_rate_limit_key(request: Request) -> str:
    """
    从 Authorization 解析 JWT user_id 作为按用户限流的键

    Detail:
        1. 此处只做轻量分桶键，不在限流路径查库；token_version 与 is_disabled 等需在鉴权依赖中校验，避免每条请求为算键访问数据库
        2. SlowAPI 的 key_func 宜保持同步；get_current_user 为异步且含 ORM，不宜嵌入键函数
        3. 访问控制仍由 get_current_user 保证；未通过鉴权时业务不执行，限流仅按 JWT 可解出的 user_id 或退回 IP 占用对应桶
        4. 若同一 key_func 挂在不要求 Bearer 的接口上，无令牌或解码失败时键与纯 IP 限流一致，该路由匿名请求按 IP 分桶；带合法 JWT 时仍按 user: 分桶，二者计数相互独立

    Args:
        request (Request): Starlette 请求对象

    Returns:
        str: user:用户 ID 无令牌或解码失败时退回客户端 IP
    """
    ip_key = get_client_ip_for_rate_limit(request)
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return ip_key

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return ip_key

    payload = TokenManager.decode(token)
    if payload is None:
        return ip_key

    user_id = payload["user_id"]
    if not user_id:
        return ip_key
    return f"user:{user_id}"
