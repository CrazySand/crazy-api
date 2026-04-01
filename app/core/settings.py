from functools import lru_cache

from pydantic import Field
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
    jwt_secret: str = Field(
        default="b7off1Hm4tRcr3xkl86HFghaC_CzgUDGrtnxVGFV9AQ",
        alias="JWT_SECRET",
    )
    jwt_ttl: int = 3600 * 24 * 7
    password_min_length: int = 8
    password_max_length: int = 16

    # 使用 Field 显式映射环境变量名，确保通过 DB_URI 注入配置
    db_uri: str = Field(
        default="mysql://a2_crazy:wHwszENzAFcwcJAD@gz.crazysand.site:3306/a2_crazy",
        alias="DB_URI",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取应用配置对象

    Returns:
        Settings: 应用配置实例
    """
    return Settings()
