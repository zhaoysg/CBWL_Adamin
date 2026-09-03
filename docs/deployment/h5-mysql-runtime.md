# 独立 H5 与 MySQL 运行配置

## 目标结构

```text
CBWL_H5 (Vue 3 静态站点)
        |
        | HTTPS /api/v1/portal/*
        v
CBWL_Adamin/backend (FastAPI)
        |
        +-- MySQL 8.x：业务与系统数据
        +-- Redis 7.x：会话、验证码、限流与缓存

CBWL_Adamin/frontend/web (管理后台)
        |
        +-- HTTPS /api/v1/*
```

H5 不包含 MySQL 驱动，不持有数据库账号，也不直接连接数据库。所有数据读写都必须通过 FastAPI 的 Portal API；管理后台和 H5 共享同一个后端业务服务与同一套 MySQL 数据。

## 数据库规则

- 开发、验收和生产运行统一使用 MySQL。
- 生产配置会拒绝 `DATABASE_TYPE=sqlite` 或 `DATABASE_TYPE=postgres`。
- 生产配置会拒绝 `localhost`、`127.0.0.1` 和 `::1` 作为 MySQL 主机。
- SQLite 仅用于 pytest 的临时、隔离测试，不保存业务数据，不允许部署。
- 所有结构调整必须提交 Alembic 迁移，并在 MySQL 8.4 CI 中至少执行一次升级验证。
- H5 商品、价格和订单扩展要在当前订单支付 PR 的迁移链稳定后再追加，避免形成多个 Alembic head。

## 后端环境变量模板

以下内容只展示变量名称和示例结构，不包含真实密码或密钥。实际值由部署环境的 Secret 管理能力注入。

```dotenv
ENVIRONMENT=prod
DEBUG=False

SECRET_KEY=<至少32位随机值>
ACCESS_TOKEN_EXPIRE_SECONDS=900
REFRESH_TOKEN_EXPIRE_SECONDS=604800
TOKEN_SLIDING_EXPIRE=False

DATABASE_TYPE=mysql
DATABASE_HOST=<MySQL服务主机，不得为localhost或127.0.0.1>
DATABASE_PORT=3306
DATABASE_USER=<最小权限应用账号>
DATABASE_PASSWORD=<由Secret注入>
DATABASE_NAME=caibuwailu
DATABASE_ECHO=False
POOL_PRE_PING=True
POOL_RECYCLE=1800

REDIS_HOST=<Redis服务主机>
REDIS_PORT=6379
REDIS_PASSWORD=<由Secret注入>
REDIS_DB_NAME=1

PROD_CORS_ORIGINS=https://admin.example.com,https://m.example.com
ALLOWED_HOSTS=["api.example.com"]
ALLOW_CREDENTIALS=True

PORTAL_ALLOWED_ORIGINS=https://m.example.com
PORTAL_ALLOWED_LOGIN_TYPES=H5,移动端
PORTAL_ALLOW_SUPERUSER_LOGIN=False
PORTAL_REFRESH_COOKIE_NAME=cbwl_portal_refresh
PORTAL_REFRESH_COOKIE_PATH=/api/v1/portal/auth
PORTAL_REFRESH_COOKIE_SECURE=True
PORTAL_REFRESH_COOKIE_SAMESITE=lax
PORTAL_RATE_LIMIT_ENABLE=True
PORTAL_CAPTCHA_ISSUE_LIMIT=20
PORTAL_CAPTCHA_ISSUE_WINDOW_SECONDS=60
PORTAL_LOGIN_ATTEMPT_LIMIT=5
PORTAL_LOGIN_ATTEMPT_WINDOW_SECONDS=300
PORTAL_CAPTCHA_TTL_SECONDS=120
```

`PORTAL_ALLOWED_LOGIN_TYPES` 中的 `移动端` 只为旧 UniApp 迁移期兼容。独立 Vue 3 H5 完成联调、部署和回滚验证后，应删除该兼容值，仅保留 `H5`。

## MySQL 账号权限

应用账号不使用 root。初始可按实际数据库名称授予：

```sql
CREATE USER 'caibuwailu_app'@'%' IDENTIFIED BY '<强密码>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON caibuwailu.* TO 'caibuwailu_app'@'%';
FLUSH PRIVILEGES;
```

如果生产迁移由独立发布账号执行，应进一步拆分：

- 运行账号：仅 `SELECT / INSERT / UPDATE / DELETE`；
- 迁移账号：在受控发布阶段临时拥有 DDL 权限；
- 禁止把 root 凭证写入仓库、H5 构建变量或浏览器代码。

## Portal 认证边界

管理后台继续使用 `/system/auth/*`，H5 使用：

```text
GET  /api/v1/portal/auth/captcha
POST /api/v1/portal/auth/login
POST /api/v1/portal/auth/refresh
POST /api/v1/portal/auth/logout
```

H5 的 Access Token 只驻留内存；Refresh Token 只由后端写入 `HttpOnly + Secure + SameSite` Cookie，并且只发送到 `/api/v1/portal/auth`。响应体不返回 Refresh Token。Portal 接口还会验证：

- JWT 类型与有效期；
- Redis 中当前 Access/Refresh Token 的精确值；
- Redis 会话是否存在；
- `login_type` 是否属于 H5；
- 管理员 `PC端` Token 不能访问 Portal；
- 超级管理员账号默认不能通过 H5 登录；
- 生产写操作的 Origin 是否在 H5 白名单中。

## 部署检查

1. 在独立 MySQL 实例或托管 MySQL 上创建数据库和最小权限账号。
2. 注入后端环境变量，确认生产启动门禁通过。
3. 执行 `alembic upgrade head`，不得使用 ORM `create_all` 替代生产迁移。
4. 验证 `/api/v1/portal/health`。
5. 从 H5 域名完成登录、刷新、退出与内容访问。
6. 验证旧 Access Token、旧 Refresh Token和管理后台 Token 均不能访问 H5 用户数据。
7. 独立 H5 CI、真实接口联调、独立部署和回滚全部通过后，才从管理平台仓库删除旧 `frontend/app`。
