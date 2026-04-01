from typing import Annotated
from uuid import UUID

from fastapi import Header

from app.core import response
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
        response.raise_unauthorized("未携带令牌或格式非法")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        response.raise_unauthorized("未携带令牌或格式非法")

    payload = TokenManager.decode(token)
    if payload is None:
        response.raise_unauthorized()

    try:
        user_uuid = UUID(payload["user_id"])
        tv = int(payload["token_version"])
    except (KeyError, ValueError, TypeError):
        response.raise_unauthorized()

    user = await User.get_or_none(user_id=user_uuid)
    if user is None or user.is_deleted:
        response.raise_unauthorized()

    if user.token_version != tv:
        response.raise_unauthorized()

    if user.is_disabled:
        response.raise_unauthorized("账号已禁用")

    return user
