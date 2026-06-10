from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.response import ApiCode, ApiResponse, ApiResponseError, build_response


def _validation_error_message(error: dict) -> str:
    """
    从 Pydantic 原始 error 项提取面向用户的消息。

    Args:
        error (dict): exc.errors() 中的单项。

    Returns:
        str: 用户可见的校验提示。
    """
    ctx = error.get("ctx")
    if isinstance(ctx, dict):
        inner = ctx.get("error")
        if isinstance(inner, BaseException):
            if inner.args:
                return str(inner.args[0])
            return str(inner)

    msg = error.get("msg", "请求参数校验失败")
    if error.get("type") == "value_error" and msg.startswith("Value error, "):
        return msg.removeprefix("Value error, ")
    return msg


def _validation_errors_for_response(raw_errors: list) -> list:
    """
    将 Pydantic 原始 errors 转为可返回客户端的结构。

    剔除 input、ctx、url，msg 使用用户可见文案。

    Args:
        raw_errors (list): exc.errors() 返回值。

    Returns:
        list: 每项仅含 type、loc、msg。
    """
    out: list = []
    for item in raw_errors:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "type": item.get("type"),
                "loc": list(item.get("loc", ())),
                "msg": _validation_error_message(item),
            }
        )
    return out


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器。

    Args:
        app (FastAPI): 应用实例。
    """

    def to_json(payload: ApiResponse) -> JSONResponse:
        """
        将统一响应体转换为 HTTP JSON 响应。

        Args:
            payload (ApiResponse): 统一响应体。

        Returns:
            JSONResponse: HTTP 200 JSON 响应。
        """
        return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        处理请求参数校验异常。

        Args:
            request (Request): 请求对象。
            exc (RequestValidationError): 参数校验异常。

        Returns:
            JSONResponse: 统一响应对象。
        """
        raw_errors = exc.errors()
        errors = _validation_errors_for_response(raw_errors)
        message = (
            _validation_error_message(raw_errors[0])
            if raw_errors
            else "请求参数校验失败"
        )

        return to_json(
            build_response(
                ApiCode.VALIDATION_ERROR,
                msg=message,
                data=errors,
                request=request,
            )
        )

    async def handle_api_response_error(
        request: Request, exc: ApiResponseError
    ) -> JSONResponse:
        """
        将 ApiResponseError 转为 HTTP JSON 响应。

        Args:
            request (Request): 请求对象。
            exc (ApiResponseError): 携带统一响应体的异常。

        Returns:
            JSONResponse: 与路由直接 return ApiResponse 时结构一致。
        """
        return to_json(build_response(exc.body.code, msg=exc.body.msg, data=exc.body.data, request=request))

    async def handle_rate_limit_exceeded(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        """
        将 SlowAPI 限流异常转为统一 JSON 响应。

        Args:
            request (Request): 请求对象。
            exc (RateLimitExceeded): 限流异常。

        Returns:
            JSONResponse: 业务码 RATE_LIMITED。
        """
        detail = getattr(exc, "detail", None)
        msg = "请求过于频繁"
        if detail:
            msg = str(detail)
        return to_json(
            build_response(
                ApiCode.RATE_LIMITED,
                msg=msg,
                request=request,
            )
        )

    app.add_exception_handler(RequestValidationError,
                              handle_request_validation_error)
    app.add_exception_handler(ApiResponseError, handle_api_response_error)
    app.add_exception_handler(RateLimitExceeded, handle_rate_limit_exceeded)
