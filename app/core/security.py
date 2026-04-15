from datetime import datetime, timezone, timedelta

import argon2
import jwt

from app.core.settings import get_settings

settings = get_settings()

JWT_ALGORITHM = "HS256"  # JWT 算法

password_hasher = argon2.PasswordHasher(
    time_cost=3,  # 迭代次数（计算成本）
    memory_cost=65536,  # 内存使用量（64MB）
    parallelism=4,  # 并行线程数
    hash_len=32,  # 哈希长度
    salt_len=16,  # 盐值长度
)


class PasswordManager:
    """高性能密码管理工具类"""

    @staticmethod
    def hash(password: str) -> str:
        """
        生成密码哈希

        Args:
            password (str): 明文密码

        Returns:
            str: 哈希后的密码字符串
        """
        # argon2 允许空密码，但出于安全考虑，这里禁止空密码
        if not password.strip():
            raise ValueError("密码不能为空或仅包含空白字符")
        return password_hasher.hash(password)

    @staticmethod
    def verify(hashed_password: str, plain_password: str) -> bool:
        """
        校验密码是否匹配

        Args:
            hashed_password (str): 哈希后的密码
            plain_password (str): 明文密码

        Returns:
            bool: 是否匹配
        """
        try:
            return password_hasher.verify(hashed_password, plain_password)
        except (
            argon2.exceptions.VerifyMismatchError,  # 明文与哈希不一致（密码错误）
            argon2.exceptions.VerificationError,    # 校验其它失败（VerifyMismatch 的基类）
            argon2.exceptions.InvalidHashError,     # 存储串非合法 argon2 哈希（损坏或历史数据）
        ):
            return False


class TokenManager:
    """用户令牌管理工具类"""

    @staticmethod
    def decode(token: str) -> dict | None:
        """
        解码访问令牌

        Args:
            token (str): 待解码的令牌

        Returns:
            dict: 解析后的令牌信息
                - user_id (str): 用户 ID
                - token_version (int): Token 版本号
            None: 令牌无效或已过期
        """
        try:
            decoded = jwt.decode(
                token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
            if (
                (user_id := decoded.get("sub")) is None
                or (token_version := decoded.get("token_version")) is None
            ):
                return None
            return {
                "user_id": user_id,
                "token_version": token_version,
            }
        # ExpiredSignatureError 表示令牌已过期 InvalidTokenError 表示令牌格式或签名等无效
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def generate(user_id: str, token_version: int, expires_in: int | None = None) -> str:
        """
        生成访问令牌

        Args:
            user_id (str): 用户 ID
            token_version (int): Token 版本号
            expires_in (int | None): 过期时间秒数

        Returns:
            str: 编码后的访问令牌
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(seconds=expires_in or settings.jwt_ttl)

        to_encode = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            # exp 是过期时间戳，在后续的 jwt 解码中会被检查
            # 如果当前时间大于过期时间，则 token 无效，抛出 jwt.ExpiredSignatureError
            "exp": int(expire.timestamp()),
            "token_version": token_version,  # 用于实现 token 作废功能
        }

        access_token = jwt.encode(
            to_encode, settings.jwt_secret, algorithm=JWT_ALGORITHM)
        return access_token
