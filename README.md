# crazy-api

FastAPI 后端，提供用户注册登录（JWT）、统一 JSON 业务码响应、访问日志与 SlowAPI 限流等。

## 运行

Python 版本见 `requirements.txt` 注释。安装依赖后：

```bash
python -m app.main
```

配置可通过环境变量覆盖，敏感项如 `JWT_SECRET`、`DB_URI` 见 `app/core/settings.py`。

## 请求体大小限制

应用在 `app/core/middleware.py` 中根据请求头 **`Content-Length`** 与配置 **`max_request_body_bytes`**（环境变量 **`MAX_REQUEST_BODY_BYTES`**，默认 `262144`）比较；超限则直接返回业务错误，**不进入路由与 JSON 解析**。设为 **`0`** 表示关闭该检查。

**边界**：未带合法 `Content-Length`（例如 **`Transfer-Encoding: chunked`**）时，应用**无法在不大块读流的前提下**得知总长度，仍会交给下游处理；若需对这类请求也硬限制，请在 **Nginx** 等反向代理侧配置 **`client_max_body_size`**（或与所用 ASGI/网关等价能力），与上述应用层限制形成互补。

## 访问日志白名单

`ApiAccessLog` 在返回统一 **`ApiResponse`** 时写入（路由中 `await response.respond_json(request, ...)`，全局异常处理器内亦会写入），**不经过**读响应体。仅当请求路径命中**白名单**、已匹配到 `endpoint` 且 **HTTP 状态码为 200**（与统一 JSON 约定一致）时写入。

配置项 **`access_log_whitelist`**：逗号分隔；路径**等于**某项，或**以「该项 + `/`」为前缀**，则允许记录。默认为 **`/api`**；需要同时记录 `/health` 时可设为 `/api,/health`。

## 访问日志排除与字段

命中白名单且**未命中排除**时，除 `method`、`path`、`duration_ms`、`client_ip` 外，记录 **`api_code` / `api_msg`**，直接取自 **`ApiResponse.code` / `ApiResponse.msg`**（`msg` 截断至与模型一致，当前 `CharField` 上限 512），**不序列化 `data`**，大字段不会影响日志性能。

- **`access_log_exclude_paths`**：逗号分隔，路径匹配规则与**白名单相同**；**命中则不写入 `ApiAccessLog`**

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
