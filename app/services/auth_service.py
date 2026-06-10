from tortoise.exceptions import IntegrityError

from app.models.user import User
from app.core.settings import get_settings
from app.core.security import PasswordManager, TokenManager

settings = get_settings()


async def register_user(username: str, password: str, nickname: str) -> User:
    """
    注册新用户并返回用户对象。

    Args:
        username (str): 登录用户名。
        password (str): 明文密码。
        nickname (str): 用户昵称。

    Returns:
        User: 新创建的用户对象。

    Raises:
        ValueError: 用户名已存在，含预检或并发下唯一约束冲突。
    """
    if await User.exists(username=username):
        raise ValueError("用户名已存在")

    hashed_password = PasswordManager.hash(password)
    try:
        user = await User.create(
            username=username,
            hashed_password=hashed_password,
            nickname=nickname,
        )
        return user
    except IntegrityError as exc:
        # 并发场景下可能绕过 exists 检查，此处统一映射为业务可读错误。
        raise ValueError("用户名已存在") from exc


async def login_user(username: str, password: str) -> User:
    """
    登录并返回用户对象。

    Args:
        username (str): 登录用户名。
        password (str): 明文密码。

    Returns:
        User: 用户对象。

    Raises:
        ValueError: 用户名不存在或密码错误。
    """
    user = await User.get_or_none(username=username)
    if user is None:
        raise ValueError("用户名不存在")
    if not PasswordManager.verify(user.hashed_password, password):
        raise ValueError("密码错误")
    return user


def create_access_token_for_user(user: User) -> str:
    """
    为已通过凭据校验的用户签发 JWT 访问令牌。

    Args:
        user (User): 已认证用户实体。

    Returns:
        str: 编码后的访问令牌。
    """
    return TokenManager.generate(
        str(user.user_id),
        user.token_version,
        expires_in=settings.jwt_ttl,
    )
