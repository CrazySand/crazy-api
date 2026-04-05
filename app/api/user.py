from fastapi import APIRouter, Request

from app.core import response
from app.core.deps import CurrentUser
from app.core.rate_limit import USER_ME_PER_USER, get_user_rate_limit_key, limiter

user_router = APIRouter()


@user_router.get("/me")
@limiter.limit(USER_ME_PER_USER, key_func=get_user_rate_limit_key)
async def get_my_profile(
    request: Request,
    user: CurrentUser,
):
    """
    获取个人信息

    Args:
        request (Request): 供 SlowAPI 限流键取值
        user (User): 当前登录用户

    Returns:
        ApiResponse: 含用户概要字段的标准响应
    """
    return await response.respond_ok(
        request,
        data={
            "user_id": str(user.user_id),
            "username": user.username,
            "nickname": user.nickname,
            "created_at": user.created_at.isoformat(),
        },
    )
