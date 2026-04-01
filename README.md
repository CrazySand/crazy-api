# crazy-api

FastAPI 后端，提供用户注册登录（JWT）、统一 JSON 业务码响应、访问日志与 SlowAPI 限流等。

## 运行

Python 版本见 `requirements.txt` 注释。安装依赖后：

```bash
python -m app.main
```

配置可通过环境变量覆盖，敏感项如 `JWT_SECRET`、`DB_URI` 见 `app/core/settings.py`。

## 访问日志白名单

`ApiAccessLog` 由中间件按规则写入。仅当请求路径命中**白名单**、已匹配到 `endpoint` 且 **HTTP 状态码为 200** 时写入（201、204 等其它 2xx 不记）。

配置项 **`access_log_whitelist`**：逗号分隔；路径**等于**某项，或**以「该项 + `/`」为前缀**，则允许记录。默认为 **`/api`**；需要同时记录 `/health` 时可设为 `/api,/health`。

## 访问日志 JSON 与排除路径

命中白名单且**未命中排除**且 HTTP 200 时，除 `method`、`path`、`duration_ms`、`client_ip` 外，可记录 **`api_code` / `api_msg`**（数据库字段，见 `app/models/api_access_log.py`）。

- **`Content-Type` 含 `application/json`** 时，中间件会读完整响应体（有 `body()` 则 `await response.body()`，否则拼接 `body_iterator`，与 Starlette 内部包装方式有关）并解析顶层 **`code`**、**`msg`**；`msg` 入库时截断至与模型字段一致的长度（当前 `CharField` 上限 512）  
- **`access_log_exclude_paths`**：逗号分隔，路径匹配规则与**白名单相同**（等于或「前缀 + `/`」子路径）；**命中则不写入 `ApiAccessLog`**。若希望「整段 `/api` 都记、只剔除少数路径」，白名单写 `/api` 并把需剔除的路径列在此处  

已有数据库需为表 `api_access_log` 增加列 **`api_code`**（可空整型）、**`api_msg`**（可空字符串，长度与模型一致），或使用 Tortoise 迁移 / `generate_schemas` 按环境执行。

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
