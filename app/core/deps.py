from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from app.core.response import raise_unauthorized
from app.core.security import TokenManager
from app.models.user import User


async def get_current_user(
    authorization: Annotated[
        str | None,
        Header(description="Bearer 方案下的 JWT，与登录接口返回的 access_token 一致"),
    ] = None,
) -> User:
    """
    从 Authorization 头解析并校验当前用户

    Args:
        authorization (str | None): 原始 Authorization 头值

    Returns:
        User: 当前登录用户实体

    Raises:
        ApiResponseError: 未携带令牌、格式非法或校验失败（响应体为未认证等业务码）
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise_unauthorized("未携带令牌或格式非法")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise_unauthorized("未携带令牌或格式非法")

    payload = TokenManager.decode(token)
    if payload is None:
        raise_unauthorized()

    try:
        user_uuid = UUID(payload["user_id"])
        tv = int(payload["token_version"])
    except (KeyError, ValueError, TypeError):
        raise_unauthorized()

    user = await User.get_or_none(user_id=user_uuid)
    if user is None or user.is_deleted:
        raise_unauthorized()

    if user.token_version != tv:
        raise_unauthorized()

    if user.is_disabled:
        raise_unauthorized("账号已禁用")

    return user


def enable_access_log(request: Request) -> None:
    """
    启用当前请求访问日志

    Args:
        request (Request): 请求对象
    """
    setattr(request.state, "enable_access_log", True)


CurrentUser = Annotated[User, Depends(get_current_user)]
