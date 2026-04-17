from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    enable_docs: bool = True
    openapi_url: str = "/openapi.json"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

    # 生成方法：python -c "import secrets; print(secrets.token_urlsafe(32))"
    jwt_secret: str = "b7off1Hm4tRcr3xkl86HFghaC_CzgUDGrtnxVGFV9AQ"
    jwt_ttl: int = 3600 * 24 * 7
    password_min_length: int = 8
    password_max_length: int = 16

    db_uri: str = "sqlite://db.sqlite3"

    # 客户端 IP 解析策略
    # auto 先 X-Real-IP 再无则 request.client
    # x_real_ip 仅用 X-Real-IP
    # direct 仅用 request.client 直连或避免伪造头时使用
    client_ip_source: Literal["auto", "x_real_ip", "direct"] = "auto"


@lru_cache
def get_settings() -> Settings:
    """
    获取应用配置对象

    Returns:
        Settings: 应用配置实例
    """
    return Settings()
