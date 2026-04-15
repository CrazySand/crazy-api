import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from app.core import access_log
from app.core.deps import enable_access_log
from app.core.rate_limit import LOGIN_PER_IP, REGISTER_PER_IP, limiter
from app.core.response import ApiCode, build_response
from app.core.settings import get_settings
from app.services import auth_service

auth_router = APIRouter()
settings = get_settings()

# ============================== 注册 ==============================


class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str

    @field_validator("username")
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", value):
            raise ValueError("用户名格式不正确，需为3-20位字母、数字或下划线")
        return value

    @field_validator("password")
    def validate_password(cls, value: str) -> str:
        if len(value) < settings.password_min_length or len(value) > settings.password_max_length:
            raise ValueError(
                f"密码长度必须为{settings.password_min_length}-{settings.password_max_length}个字符"
            )
        if any(ch.isspace() for ch in value):
            raise ValueError("密码不能包含空白字符")
        if not all(33 <= ord(ch) <= 126 for ch in value):
            raise ValueError("密码仅支持可打印 ASCII 字符")
        return value

    @field_validator("nickname")
    def validate_nickname(cls, value: str) -> str:
        value = value.strip()  # 去除前后空白字符
        if len(value) < 1 or len(value) > 24:
            raise ValueError("昵称长度必须为1-24个字符")
        if not all(ch.isprintable() for ch in value):
            raise ValueError("昵称不能包含控制字符")
        return value


@auth_router.post("/register", dependencies=[Depends(enable_access_log)])
@limiter.limit(REGISTER_PER_IP)
async def register(request: Request, payload: RegisterRequest):
    """注册"""
    try:
        user = await auth_service.register_user(payload.username, payload.password, payload.nickname)
        return build_response(
            ApiCode.OK,
            msg="注册成功",
            data={
                "user_id": str(user.user_id),
                "username": user.username,
                "nickname": user.nickname,
            },
        )
    except ValueError as exc:
        return build_response(ApiCode.BAD_REQUEST, msg=str(exc))

# ============================== 登录 ==============================


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", value):
            raise ValueError("用户名格式不正确，需为3-20位字母、数字或下划线")
        return value

    @field_validator("password")
    def validate_password(cls, value: str) -> str:
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("密码不能为空且不能包含空白字符")
        if len(value) > settings.password_max_length:
            raise ValueError(f"密码长度不能超过{settings.password_max_length}个字符")
        return value


@auth_router.post("/login", dependencies=[Depends(enable_access_log)])
@limiter.limit(LOGIN_PER_IP)
async def login(request: Request, payload: LoginRequest):
    """登录"""
    try:
        user = await auth_service.login_user(payload.username, payload.password)
        access_token = auth_service.create_access_token_for_user(user)
        # 登录成功后先写入日志 user_id 上下文 仅用于访问日志归属 不参与鉴权判定
        access_log.set_access_log_user_id(request, user.user_id)
        return build_response(
            ApiCode.OK,
            msg="登录成功",
            data={
                "nickname": user.nickname,
                "access_token": access_token,
            },
        )
    except ValueError as exc:
        return build_response(ApiCode.BAD_REQUEST, msg=str(exc))
