import re

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from app.core import access_log
from app.core.rate_limit import LOGIN_PER_IP, REGISTER_PER_IP, limiter
from app.core.settings import get_settings
from app.services import auth_service
from app.core import response


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


@auth_router.post("/register")
@limiter.limit(REGISTER_PER_IP)
async def register(request: Request, payload: RegisterRequest):
    """注册"""
    try:
        user = await auth_service.register_user(payload.username, payload.password, payload.nickname)
        return await response.respond_ok(
            request,
            msg="注册成功",
            data={
                "user_id": str(user.user_id),
                "username": user.username,
                "nickname": user.nickname,
            },
        )
    except ValueError as exc:
        return await response.respond_bad_request(request, msg=str(exc))

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


@auth_router.post("/login")
@limiter.limit(LOGIN_PER_IP)
async def login(request: Request, payload: LoginRequest):
    """登录"""
    try:
        user = await auth_service.login_user(payload.username, payload.password)
        access_token = auth_service.create_access_token_for_user(user)
        access_log.set_access_log_user_id(request, user.user_id)
        return await response.respond_ok(
            request,
            msg="登录成功",
            data={
                "nickname": user.nickname,
                "access_token": access_token,
            },
        )
    except ValueError as exc:
        return await response.respond_bad_request(request, msg=str(exc))
