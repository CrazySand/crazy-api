# crazy-api

FastAPI 后端，提供用户注册登录（JWT）、统一 JSON 业务码响应、访问日志与 SlowAPI 限流等。

## 运行

Python 版本见 `requirements.txt` 注释。安装依赖后：

```bash
python -m app
```

配置可通过环境变量覆盖，敏感项如 `JWT_SECRET`、`DB_URI` 见 `app/core/settings.py`。

## 统一响应约定

业务接口统一返回 `app/core/response.py` 中的 `build_response(...)` 结果（`ApiResponse` 结构：`code`、`msg`、`data`）。异常场景同样返回该结构。

当接口启用了访问日志时，建议调用 `build_response(..., request=request)`，将 `api_code` 与 `api_msg` 写入 `request.state`，供中间件落库时直接读取。

## 请求体与响应体大小

应用内**不做**请求体大小或数据包尺寸的校验与限制，请在 **Nginx**（或等价反向代理）侧配置，例如 **`client_max_body_size`** 限制上传体，必要时再配合 **`proxy_buffer_size`** 等与代理缓冲相关的指令，由网关统一约束流量形态。

## 访问日志启用方式

`ApiAccessLog` 默认不记录。仅在路由上显式添加依赖 **`Depends(enable_access_log)`** 时，才会在响应返回后按下面流程尝试写入。

示例：

```python
from fastapi import Depends
from app.core.deps import enable_access_log

@router.get("/me", dependencies=[Depends(enable_access_log)])
async def me(...):
    ...
```

日志写入流程：

1. 依赖 `enable_access_log` 将 `request.state.enable_access_log` 置为 `True`
2. 路由/异常处理器通过 `build_response(..., request=request)` 将 `api_code`、`api_msg` 写入 `request.state`
3. `finalize_response` 只计算本次请求 `elapsed_ms`，并读取 `request.state` 中的日志上下文后一次写入 `ApiAccessLog`

说明：登录接口在签发令牌前无 Bearer 头，因此会在路由内通过 `set_access_log_user_id(...)` 先写入 `request.state`，用于日志中的 `user_id`

## 访问日志字段

启用后，记录 `method`、`path`、`duration_ms`、`client_ip`、`api_code`、`api_msg`。其中 `api_code`/`api_msg` 来自 `request.state` 中的响应上下文（由 `build_response(..., request=request)` 写入，`msg` 会截断至模型上限，`data` 不入库）。

耗时口径：`duration_ms` 与响应头 `X-Process-Time` 使用同一 `elapsed_ms`，均为**全链路耗时**（包含访问日志写库）；仅展示单位不同（前者毫秒整数，后者秒小数）。

若接口未写入响应上下文（例如未通过 `build_response(..., request=request)` 返回），`api_code`/`api_msg` 可能为空，但仍会写入访问日志基础字段。

边界：在 **Nginx** 等网关阶段被拒绝的请求不会进入应用，因此不会触发 `enable_access_log`，也不会写入 `ApiAccessLog`

已有数据库需为表 `api_access_log` 配置列 **`api_code`**、**`api_msg`**（见 `app/models/api_access_log.py`），或使用 Tortoise 迁移 / `generate_schemas` 按环境执行。

## 客户端 IP 与会话约定（`client_ip_source`）

访问日志 `client_ip` 与 SlowAPI 按 IP 限流键均通过 `app/core/client_ip.py` 解析，由 **`client_ip_source`** 控制，取值：

| 取值 | 含义 |
|------|------|
| `auto`（默认） | 先读请求头 **`X-Real-IP`**，没有则使用 **`request.client.host`**（直连调试常见） |
| `x_real_ip` | **只**读 `X-Real-IP`，无则视为无 IP（限流键会回退为 `127.0.0.1`） |
| `direct` | **只**用 `request.client.host`，**忽略** `X-Real-IP`（直连公网、担心伪造头时用） |

在 **Nginx 等可信反代** 后部署且希望日志与限流按**真实用户**分桶时：设 `CLIENT_IP_SOURCE=auto` 或 `x_real_ip`，并在 Nginx 写入 `X-Real-IP`，例如：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**安全说明**：仅在「外网用户无法绕过反代直连应用端口」时，依赖 `X-Real-IP` 才可视为可信；应用若对外直连暴露，恶意客户端可伪造该头，此时应使用 `direct` 或仅在内网监听。

## 反向代理与 SlowAPI

反代未传真实 IP 时，`request.client` 往往是代理地址，所有人可能共用一个 IP，导致按 IP 限流失真；与上表配合选择 `CLIENT_IP_SOURCE` 即可。
