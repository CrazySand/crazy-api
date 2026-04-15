from tortoise import fields
from tortoise.models import Model


class ApiAccessLog(Model):
    """单次 HTTP 接口访问审计记录"""

    id = fields.IntField(pk=True)                            # 自增主键
    user_id = fields.UUIDField(null=True)                    # 业务用户 UUID 匿名为 NULL
    method = fields.CharField(max_length=8)                  # HTTP 方法如 GET POST
    path = fields.CharField(max_length=512)                  # 不含 query 的路径
    api_code = fields.IntField(null=True)                    # 从 JSON body 解析的 code 成功写入时有值 历史数据可为 NULL
    api_msg = fields.CharField(max_length=512, null=True)    # 从 JSON body 解析的 msg 已截断
    duration_ms = fields.IntField()                          # 内层中间件耗时毫秒
    client_ip = fields.CharField(max_length=45, null=True)   # 见 client_ip_source 策略
    created_at = fields.DatetimeField(auto_now_add=True)     # 记录创建时间

    class Meta:
        table = "api_access_log"
