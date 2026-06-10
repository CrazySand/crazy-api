from enum import IntEnum
from typing import NoReturn

from fastapi import Request
from pydantic import BaseModel

from app.core.access_log import set_access_log_result


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
    携带统一 ApiResponse 的业务异常，供全局处理器序列化后返回客户端。
    """

    def __init__(self, body: ApiResponse) -> None:
        """
        绑定待返回的统一响应体。

        Args:
            body (ApiResponse): 与 response 模块工厂函数构造结果一致。
        """
        self.body = body
        super().__init__(body.msg)


def build_response(
    code: ApiCode,
    msg: str,
    data: dict | list | None = None,
    request: Request | None = None,
) -> ApiResponse:
    """
    构建统一响应对象。

    Args:
        code (ApiCode): 业务状态码。
        msg (str): 响应消息。
        data (dict | list | None): 响应数据。
        request (Request | None): 请求对象，缺省时不写日志上下文。

    Returns:
        ApiResponse: 统一响应对象。
    """
    if request is not None:
        set_access_log_result(request, code, msg)
    return ApiResponse(code=code, msg=msg, data=data)


def raise_unauthorized(
    msg: str = "未登录或令牌无效",
    data: dict | list | None = None,
) -> NoReturn:
    """
    抛出未认证 ApiResponseError，供全局异常处理器序列化为 HTTP 响应。

    Args:
        msg (str): 响应消息。
        data (dict | list | None): 响应数据。

    Raises:
        ApiResponseError: 始终抛出，且 body 为未认证业务码。
    """
    raise ApiResponseError(build_response(ApiCode.UNAUTHORIZED, msg, data))
