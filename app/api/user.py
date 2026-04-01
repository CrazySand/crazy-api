from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core import response
from app.core.deps import get_current_user
from app.core.rate_limit import USER_ME_PER_USER, get_user_rate_limit_key, limiter
from app.models.user import User

user_router = APIRouter()


@user_router.get("/me")
@limiter.limit(USER_ME_PER_USER, key_func=get_user_rate_limit_key)
async def get_my_profile(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    获取个人信息

    Args:
        request (Request): 供 SlowAPI 限流键取值
        user (User): 当前登录用户

    Returns:
        ApiResponse: 含用户概要字段的标准响应
    """
    _ = request
    return response.ok(
        data={
            "user_id": str(user.user_id),
            "username": user.username,
            "nickname": user.nickname,
            "created_at": user.created_at.isoformat(),
        },
    )
