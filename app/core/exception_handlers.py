from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core import response
from app.core.response import ApiResponseError


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器

    Args:
        app (FastAPI): 应用实例
    """

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
        _ = request  # 标记 request 参数当前未使用
        errors = jsonable_encoder(exc.errors())
        first_error = errors[0] if errors else None
        message = "请求参数校验失败"
        if first_error:
            message = first_error.get("msg", message)

        payload = response.validation_error(msg=message, data=errors)
        return JSONResponse(
            status_code=200,
            content=payload.model_dump(mode="json"),
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
        _ = request
        return JSONResponse(
            status_code=200,
            content=exc.body.model_dump(mode="json"),
        )

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
        _ = request
        detail = getattr(exc, "detail", None)
        msg = "请求过于频繁"
        if detail:
            msg = str(detail)
        payload = response.rate_limited(msg=msg)
        return JSONResponse(
            status_code=200,
            content=payload.model_dump(mode="json"),
        )

    app.add_exception_handler(RequestValidationError,
                              handle_request_validation_error)
    app.add_exception_handler(ApiResponseError, handle_api_response_error)
    app.add_exception_handler(RateLimitExceeded, handle_rate_limit_exceeded)
