from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.response import ApiCode, ApiResponse, ApiResponseError, build_response


def _validation_errors_for_response(errors: list) -> list:
    """
    剔除校验错误中 Pydantic 的 input 字段 避免超大或恶意内容回显

    Args:
        errors (list): jsonable_encoder 后的错误项列表

    Returns:
        list: 每项为已去掉 input 的 dict 副本
    """
    out: list = []
    for item in errors:
        if isinstance(item, dict):
            out.append(
                {k: v for k, v in item.items() if k != "input"}
            )
        else:
            out.append(item)
    return out


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器

    Args:
        app (FastAPI): 应用实例
    """

    def to_json(payload: ApiResponse) -> JSONResponse:
        """
        将统一响应体转换为 HTTP JSON 响应

        Args:
            payload (ApiResponse): 统一响应体

        Returns:
            JSONResponse: HTTP 200 JSON 响应
        """
        return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        处理请求参数校验异常

        Args:
            request (Request): 请求对象
            exc (RequestValidationError): 参数校验异常

        Returns:
            JSONResponse: 统一响应对象
        """
        errors = _validation_errors_for_response(
            jsonable_encoder(exc.errors()))
        first_error = errors[0] if errors else None
        message = "请求参数校验失败"
        if first_error:
            message = first_error.get("msg", message)

        return to_json(
            build_response(
                ApiCode.VALIDATION_ERROR,
                msg=message,
                data=errors,
            )
        )

    async def handle_api_response_error(
        request: Request, exc: ApiResponseError
    ) -> JSONResponse:
        """
        将 ApiResponseError 转为 HTTP JSON 响应

        Args:
            request (Request): 请求对象
            exc (ApiResponseError): 携带统一响应体的异常

        Returns:
            JSONResponse: 与路由直接 return ApiResponse 时结构一致
        """
        return to_json(exc.body)

    async def handle_rate_limit_exceeded(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        """
        将 SlowAPI 限流异常转为统一 JSON 响应

        Args:
            request (Request): 请求对象
            exc (RateLimitExceeded): 限流异常

        Returns:
            JSONResponse: 业务码 RATE_LIMITED
        """
        detail = getattr(exc, "detail", None)
        msg = "请求过于频繁"
        if detail:
            msg = str(detail)
        return to_json(
            build_response(
                ApiCode.RATE_LIMITED,
                msg=msg,
            )
        )

    app.add_exception_handler(RequestValidationError,
                              handle_request_validation_error)
    app.add_exception_handler(ApiResponseError, handle_api_response_error)
    app.add_exception_handler(RateLimitExceeded, handle_rate_limit_exceeded)
