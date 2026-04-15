from fastapi import APIRouter, Depends, Request

from app.core.deps import CurrentUser, enable_access_log
from app.core.rate_limit import USER_ME_PER_USER, get_user_rate_limit_key, limiter
from app.core.response import ApiCode, build_response

user_router = APIRouter()


@user_router.get("/me", dependencies=[Depends(enable_access_log)])
@limiter.limit(USER_ME_PER_USER, key_func=get_user_rate_limit_key)
async def get_my_profile(
    request: Request,
    user: CurrentUser,
):
    """获取个人信息"""
    return build_response(
        ApiCode.OK,
        msg="获取成功",
        data={
            "user_id": str(user.user_id),
            "username": user.username,
            "nickname": user.nickname,
            "created_at": user.created_at.isoformat(),
        },
    )
