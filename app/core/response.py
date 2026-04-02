from enum import IntEnum
from typing import NoReturn

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiCode(IntEnum):
    OK = 10000                  # 请求成功
    BAD_REQUEST = 10400         # 请求参数错误
    UNAUTHORIZED = 10401        # 未认证或登录失效
    FORBIDDEN = 10403           # 已认证但无权限
    NOT_FOUND = 10404           # 资源不存在
    VALIDATION_ERROR = 10422    # 参数校验失败
    RATE_LIMITED = 10429        # 请求过于频繁
    INTERNAL_ERROR = 10500      # 服务器内部错误


class ApiResponse(BaseModel):
    code: ApiCode
    msg: str
    data: dict | list | None = None


class ApiResponseError(Exception):
    """
    携带统一 ApiResponse 的业务异常 供全局处理器序列化后返回客户端
    """

    def __init__(self, body: ApiResponse) -> None:
        """
        绑定待返回的统一响应体

        Args:
            body (ApiResponse): 与 response 模块工厂函数构造结果一致
        """
        self.body = body
        super().__init__(body.msg)


def build_response(code: ApiCode, msg: str, data: dict | list | None = None) -> ApiResponse:
    """
    构建统一响应对象

    Args:
        code (ApiCode): 业务状态码
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        ApiResponse: 统一响应对象
    """
    return ApiResponse(code=code, msg=msg, data=data)


async def respond_json(request: Request, body: ApiResponse) -> JSONResponse:
    """
    将 ApiResponse 序列化为 JSON 响应并写入访问日志

    Args:
        request (Request): 请求对象
        body (ApiResponse): 统一响应体

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    from app.core.access_log import record_api_access_log

    await record_api_access_log(request, body)
    return JSONResponse(
        status_code=200,
        content=body.model_dump(mode="json"),
    )

# =========================================================


def raise_unauthorized(
    msg: str = "未登录或令牌无效",
    data: dict | list | None = None,
) -> NoReturn:
    """
    抛出未认证 ApiResponseError 供全局异常处理器序列化为 HTTP 响应

    Args:
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Raises:
        ApiResponseError: 始终抛出 且 body 为未认证业务码
    """
    raise ApiResponseError(build_response(ApiCode.UNAUTHORIZED, msg, data))

# =========================================================


async def respond_ok(
    request: Request,
    msg: str = "ok",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    成功响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.OK, msg, data))


async def respond_bad_request(
    request: Request,
    msg: str = "bad request",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    参数错误响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.BAD_REQUEST, msg, data))


async def respond_unauthorized(
    request: Request,
    msg: str = "unauthorized",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    未认证响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.UNAUTHORIZED, msg, data))


async def respond_forbidden(
    request: Request,
    msg: str = "forbidden",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    无权限响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.FORBIDDEN, msg, data))


async def respond_not_found(
    request: Request,
    msg: str = "not found",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    资源不存在响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.NOT_FOUND, msg, data))


async def respond_validation_error(
    request: Request,
    msg: str = "validation error",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    参数校验失败响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.VALIDATION_ERROR, msg, data))


async def respond_rate_limited(
    request: Request,
    msg: str = "rate limited",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    请求过于频繁响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.RATE_LIMITED, msg, data))


async def respond_internal_error(
    request: Request,
    msg: str = "internal error",
    data: dict | list | None = None,
) -> JSONResponse:
    """
    服务器内部错误响应写入访问日志并返回 JSON

    Args:
        request (Request): 请求对象
        msg (str): 响应消息
        data (dict | list | None): 响应数据

    Returns:
        JSONResponse: HTTP 200 JSON 响应
    """
    return await respond_json(request, build_response(ApiCode.INTERNAL_ERROR, msg, data))
