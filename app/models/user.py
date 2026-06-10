from uuid import uuid4

from tortoise import fields
from tortoise.models import Model


class User(Model):
    """
    用户账户实体。

    token_version 与 JWT 载荷中同名字段一致。
    库中递增后会使该用户此前签发的所有访问令牌失效。
    适用于改密、安全事件、全员登出等场景。
    若只需退出当前浏览器或设备，应通过会话级撤销实现，不宜仅依赖递增本字段。
    """

    id = fields.IntField(pk=True)                            # 自增主键
    user_id = fields.UUIDField(unique=True, default=uuid4)   # 用户业务唯一 ID
    username = fields.CharField(max_length=32, unique=True)  # 登录用户名
    hashed_password = fields.CharField(max_length=255)       # 哈希后的密码
    nickname = fields.CharField(max_length=32)               # 用户昵称
    is_disabled = fields.BooleanField(default=False)         # 是否禁用账号
    token_version = fields.IntField(default=0)               # JWT 全局作废版本号
    is_deleted = fields.BooleanField(default=False)          # 逻辑删除标记
    created_at = fields.DatetimeField(auto_now_add=True)     # 创建时间
    updated_at = fields.DatetimeField(auto_now=True)         # 更新时间

    class Meta:
        table = "user"
