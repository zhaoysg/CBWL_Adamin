# Backend 开发规范

本文件适用于 `backend/`。它在根目录 [`AGENTS.md`](../AGENTS.md) 基础上补充 FastAPI 后端规则；冲突时以更严格且更接近目标文件的规则为准。

## 1. 环境与事实来源

- Python 版本以 `.python-version` 和 `pyproject.toml` 为准，当前为 3.12+。
- 使用 `uv` 管理开发环境和 `uv.lock`；不要直接修改锁文件。
- 依赖、Ruff 和 pytest 配置以 `pyproject.toml` 为准；`requirements.txt` 是生产安装清单，依赖变更时必须评估两者是否需要同步。
- 所有命令默认在 `backend/` 执行。

## 2. 模块结构与职责

业务能力优先放在 `app/api/v1/module_<domain>/<feature>/`，沿用已有纵向模块结构：

```text
feature/
├── controller.py   # HTTP 边界、依赖注入、权限、响应编排
├── service.py      # 业务规则、跨实体流程、事务内编排
├── crud.py         # 查询与持久化操作
├── model.py        # SQLAlchemy ORM 模型
├── schema.py       # Pydantic 请求、查询、响应模型
└── __init__.py     # 显式导出或路由聚合
```

- `controller.py` 不写复杂业务规则，不直接拼 SQL，不绕过 service 调用 CRUD。
- `service.py` 不解析 HTTP 对象；除上传等边界类型外，优先接收明确的 schema/基础类型并返回 schema。
- `crud.py` 负责数据访问，不承载权限决策和跨领域业务流程；优先复用 `CRUDBase`。
- `model.py` 只定义持久化模型和必要关系；`schema.py` 明确区分创建、更新、查询和输出语义。
- 新模块必须按现有 `APIRouter` 聚合或插件发现机制注册，不创建第二套路由发现框架。
- 修改代码生成器产物约定时，优先修改 `templates/` 中的模板，并验证生成结果；不要只修一份已生成示例。

## 3. API 与权限

- 路由前缀、标签、响应模型、状态码和依赖注入沿用相邻 Controller 写法。
- 受保护接口必须通过 `AuthPermission`/`Security` 执行服务端鉴权；权限码格式保持 `module:resource:action` 的既有约定。
- 使用项目统一的 `SuccessResponse`、`StreamResponse`、`ResponseSchema` 和分页 schema，不另建平行响应格式。
- 请求参数使用 Pydantic/FastAPI 约束声明，不能只在 service 中用字符串判断补救。
- 公开接口必须显式评估限流、枚举账号、暴力破解、验证码、重放和敏感错误信息风险。
- 下载文件的文件名、媒体类型、编码和 `Content-Disposition` 必须正确；不将不可信文件名直接写入响应头。

## 4. 异步、数据库与事务

- 数据库、Redis、HTTP 和文件等 I/O 优先使用异步实现；不得在 `async def` 中直接执行长耗时同步 I/O。
- 通过已有 `db_getter`/`AsyncSession` 管理会话，不在业务函数中随意创建全局 session。
- service 组织业务原子性，CRUD 使用 `flush` 获取中间结果；事务提交/回滚遵循现有请求生命周期，不在多层重复提交。
- 查询关联数据时明确 preload/加载策略，避免循环中的 N+1 查询；分页查询必须有稳定排序。
- 批量写入先完成整体验证，再修改数据；部分成功必须是明确的产品语义并返回可审计结果。
- ORM 结构变化必须生成和审查 Alembic 迁移。迁移脚本要处理存量数据，不能仅依赖空库成功。
- SQL 或筛选表达式必须使用项目安全的结构化接口和参数绑定，禁止拼接用户输入。

## 5. Schema、类型和错误

- 新增或修改的函数必须有准确类型；避免无边界的 `Any`、裸 `dict` 和未解释的 `# type: ignore`。
- 创建模型通常使用明确必填字段；更新模型应区分“未提供”和“显式置空”，正确使用 `exclude_unset`/`exclude_none`。
- 输出使用 Pydantic schema 验证 ORM 数据，不能把 ORM 对象或内部异常直接暴露给客户端。
- 业务可预期错误使用项目现有异常类型；日志记录诊断上下文，但响应只返回安全、稳定的信息。
- 不捕获 `Exception` 后返回成功或静默继续；如需转换异常，保留异常链并确保事务回滚。

## 6. 安全规则

- 密码只存强哈希；认证和密码流程复用 `app/core/security.py`、`password_util.py` 等已有能力。
- Token、验证码、OAuth state、密码重置和会话数据必须有有效期，并评估单次使用与撤销。
- 用户、角色、部门、菜单等管理接口必须同时检查功能权限和数据范围，不能信任客户端传入的身份/租户字段。
- 上传路径必须通过 `upload_util.py` 等统一能力约束，防止路径穿越、扩展名欺骗和覆盖。
- 日志与审计记录不得保存明文密码、Token、Cookie、私钥或完整敏感数据。

## 7. 测试规则

- 测试放在 `tests/`，文件命名 `test_*.py`，异步测试遵循 pytest-asyncio 现有配置。
- service/CRUD 变更优先写能断言业务结果和数据库状态的测试；API 变更断言状态码、响应结构、权限和副作用。
- 仅断言“路由不是 404”不能证明业务正确；新增关键行为不得只使用 `assert_route` 的宽松模式。
- 缺陷修复先写失败用例；授权、事务、批量操作、边界值和异常路径属于高优先级覆盖项。
- 测试必须隔离外部服务，不访问真实生产数据库、Redis、第三方 API 或真实账号。

## 8. 验证命令

```powershell
# 安装/同步开发环境
uv sync --frozen

# 非修改式静态检查
uv run ruff check --no-fix .
uv run ruff format --check .

# 完整测试
uv run pytest -q

# 单文件或单用例快速反馈
uv run pytest -q tests/test_main.py
uv run pytest -q tests/test_api_module_system.py -k user
```

`pyproject.toml` 当前启用了 Ruff 自动修复配置，因此验证时必须显式使用 `--no-fix`；确需自动修复时仅对任务相关路径执行，并在之后复核 `git diff`。

模型变化时，在配置好的非生产环境验证：

```powershell
uv run python main.py revision --env=dev
uv run python main.py upgrade --env=dev
```

禁止为了“试一下”连接或迁移生产数据库。

## 9. Backend Code Review Rules

- 阻止缺失鉴权/数据权限、SQL 注入、路径穿越、敏感信息泄露和不安全密码处理。
- 阻止在异步请求中执行阻塞 I/O、遗漏事务回滚、非确定分页和明显 N+1 查询。
- 阻止 Controller 承载业务逻辑、Service 直接返回不受控 ORM 数据，以及 API 合约无迁移说明地破坏兼容性。
- 阻止只验证路由存在、吞掉服务端异常或依赖测试执行顺序的测试。
