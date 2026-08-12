# CBWL Admin 工程质量规范研究与落地建议

> 文档性质：研究结论，不是已经生效的项目规范
>
> 研究日期：2026-08-12
>
> 适用仓库：`CBWL_Adamin`
>
> 技术栈：Python 3.12 / FastAPI / SQLAlchemy / pytest / Ruff / uv；Vue 3 / TypeScript / Vite / Vitest / ESLint / Prettier / Stylelint / pnpm；Docker / GitHub

## 1. 结论先行

这个项目不适合把所有规则都塞进一个很长的 `AGENTS.md`。更稳妥的结构是：

1. 根 `AGENTS.md` 只做“入口、红线和导航”，控制在约 100 行上下。
2. `backend/AGENTS.md`、`frontend/web/AGENTS.md`、必要时 `docker/AGENTS.md` 只描述各自目录独有的约束与验证命令。
3. 详细、可长期维护的工程知识放进 `docs/`，把 `AGENTS.md` 当目录而不是百科全书。
4. 能由工具验证的规则不要只写成文字，必须同时落到 Ruff、类型检查、测试、commitlint、CI 和 GitHub 分支保护中。
5. 本项目当前最优先的工作不是再增加很多工具，而是先让已有工具形成一条真正执行的、非变异式的根级 CI 质量门禁。

这里必须区分两类内容：

- **规范事实**：由官方规范或工具文档明确规定，例如 Conventional Commits 的消息结构、GitHub Actions 的工作流目录位置。
- **项目建议**：结合本仓库规模和技术栈作出的治理选择，例如采用单主干还是 `dev` 长期分支、覆盖率阈值定多少。这些不是行业唯一答案，必须由项目明确选定并保持一致。

## 2. 只读仓库检查结果

### 2.1 已具备的基础

| 领域 | 已核实事实 | 证据 |
| --- | --- | --- |
| Python 运行时 | 要求 Python `>=3.12`，使用 `uv.lock` | `backend/pyproject.toml`、`backend/uv.lock` |
| Python lint/format | 已配置 Ruff，当前版本固定为 `0.14.13` | `backend/pyproject.toml` |
| Python 测试 | 已配置 pytest、pytest-asyncio，现有测试函数约 95 个 | `backend/pyproject.toml`、`backend/tests/` |
| 前端类型与测试 | 已配置 TypeScript、`vue-tsc`、Vitest | `frontend/web/package.json`、`frontend/web/vitest.config.ts` |
| 前端静态检查 | 已配置 ESLint、Prettier、Stylelint | `frontend/web/package.json` 及相应配置文件 |
| 提交消息 | 已配置 Husky、commitlint、Commitizen，类型大体遵循 Conventional Commits | `frontend/web/.husky/`、`frontend/web/commitlint.config.cjs` |
| 贡献说明 | 已有 `CONTRIBUTING.md`，描述分支与 PR 流程 | `CONTRIBUTING.md` |
| 容器化 | 已有 Dockerfile、Compose 和部署文档 | `docker/` |

### 2.2 已发现的质量治理缺口

以下是**仓库事实**，不是推测：

| 优先级 | 问题 | 影响 |
| --- | --- | --- |
| P0 | 根目录没有 `AGENTS.md`，也没有后端/前端分层代理说明 | 人和编码代理缺少统一范围、红线、完成定义和验证入口 |
| P0 | GitHub Actions 文件在 `frontend/web/.github/workflows/ci.yml`，不在仓库根 `.github/workflows/` | GitHub 不会把它识别为本仓库工作流；GitHub 明确只从仓库根目录的该路径发现工作流 |
| P0 | 当前 CI 仅覆盖前端，不覆盖后端 Ruff、测试、依赖锁一致性和安全检查 | 后端改动没有自动合并门禁 |
| P0 | 前端 `pnpm lint` 会调用 ESLint `--fix`、Prettier `--write`、Stylelint `--fix` | CI 检查会修改工作区；“修复命令”和“只读检查命令”没有分离 |
| P1 | `frontend/web/package-lock.json` 与 `pnpm-lock.yaml` 同时被 Git 跟踪，而项目声明包管理器为 pnpm | 依赖解析存在双重事实源，容易漂移 |
| P1 | 根 `CONTRIBUTING.md` 要求 PR 到 `dev`，现有工作流的 PR 目标却是 `master`，当前分支也是 `master` | 主分支策略不一致，分支保护和门禁无法可靠配置 |
| P1 | `backend/pyproject.toml` 与 `backend/requirements.txt` 同时存在，但没有写明哪个是权威源、另一个如何生成 | 依赖变更可能漏同步，开发和生产环境可能不同 |
| P1 | 后端尚未配置静态类型检查；前端已有类型检查但现有 CI 实际不生效 | 边界模型与跨层调用错误更多依赖运行时发现 |
| P1 | 没有根级 PR 模板、`CODEOWNERS`、`SECURITY.md`、分支保护说明 | 评审输入不稳定，敏感目录缺少明确责任人，漏洞报告流程缺失 |
| P2 | 缺少统一架构、质量门禁、测试策略、发布流程和 ADR 文档 | 规则容易散落在 README、配置与口头约定中并逐渐漂移 |

GitHub 的官方事实是：工作流 YAML **必须**位于仓库根目录的 `.github/workflows`；GitHub 会在事件对应的提交或引用中扫描这个根级目录。因此当前嵌套工作流不会成为本仓库的 Actions 门禁。来源：[GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)、[GitHub Workflows](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)。

## 3. `AGENTS.md` 的专业分层方式

### 3.1 官方可确认的行为

**规范事实：** OpenAI 说明 `AGENTS.md` 可用于告诉 Codex 如何浏览代码库、运行哪些测试，以及如何遵循项目实践；目录树中更深层的说明可以为局部代码提供更具体的约束。来源：[Introducing Codex](https://openai.com/index/introducing-codex/)、[Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)。

**规范事实：** OpenAI 的实际工程经验不建议使用一个巨型 `AGENTS.md`，而是用短文件作为地图，把结构化 `docs/` 当作可版本化的事实源，并通过 CI 防止文档和代码漂移。来源：[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)。

### 3.2 建议的文件结构

```text
AGENTS.md                         # 全仓入口：范围、红线、地图、最小验证
ARCHITECTURE.md                   # 系统边界和依赖方向的短入口
backend/
├── AGENTS.md                     # Python/FastAPI/数据库迁移/后端测试专属规则
└── ...
frontend/web/
├── AGENTS.md                     # Vue/TS/组件/API/前端测试专属规则
└── ...
docker/
├── AGENTS.md                     # 仅在容器约束确实较多时创建
└── ...
docs/
├── README.md                     # 文档索引与责任人
├── architecture/
│   ├── system-context.md
│   ├── backend.md
│   ├── frontend.md
│   └── data-and-migrations.md
├── engineering/
│   ├── code-quality.md
│   ├── testing-strategy.md
│   ├── git-workflow.md
│   ├── pull-request-checklist.md
│   ├── dependency-policy.md
│   └── release-process.md
├── adr/
│   ├── README.md
│   └── 0001-*.md
├── operations/
│   ├── local-development.md
│   ├── deployment.md
│   └── troubleshooting.md
├── security/
│   ├── secure-coding.md
│   └── threat-model.md
└── references/
    └── engineering-standards-research.md
```

这是**项目建议**，不是 OpenAI 强制目录。关键原则是：入口短、作用域明确、深层文件只写局部差异、详细知识有单一事实源。

### 3.3 根 `AGENTS.md` 应写什么

建议只保留会直接改变执行行为的内容：

1. 项目目的、技术栈和目录地图。
2. 指令适用范围及“更深层文件覆盖局部规则”的说明。
3. 全仓红线：不提交秘密、不改生成产物、不绕过测试、不吞异常、不做无关重构、不破坏兼容性。
4. 修改边界：只改任务相关文件；数据库、鉴权、依赖、部署属于高风险变更。
5. 最小完成定义：检查差异、补测试、运行对应门禁、报告未验证项。
6. 根级常用命令或指向详细文档的链接。
7. Git/PR 的最小规则和详细规范链接。

不建议放入：

- 大段框架教程；
- 每个模块的类名清单；
- 容易过时的完整目录树；
- 与工具配置重复的每一条 lint 规则；
- 无法执行、无法验证的口号式要求，如“必须写优雅代码”。

### 3.4 下级 `AGENTS.md` 的边界

#### `backend/AGENTS.md`

建议写：

- FastAPI 路由、service、repository/CRUD、schema/model 的依赖方向；
- async 调用、事务、异常、日志、响应模型约束；
- Alembic 迁移何时必须创建，以及升级/回滚验证；
- 时间、时区、金额、ID、分页和序列化规则；
- 后端检查命令及测试数据隔离规则；
- 鉴权、上传、SQL、模板渲染等安全敏感路径。

#### `frontend/web/AGENTS.md`

建议写：

- Vue SFC、composable、store、API client、view/component 的职责边界；
- TypeScript 不使用无理由 `any`，API 边界必须具备类型；
- 状态、请求、错误、权限、路由、i18n 的项目约定；
- UI 变更需要的响应式、键盘可用性和截图验证；
- 前端只读检查、测试和构建命令；
- 禁止手工修改自动生成文件的范围。

#### `docker/AGENTS.md`

只有当容器相关规则超过几条时再创建，避免为了“结构完整”制造空文件。内容可包括：非 root 用户、镜像固定、健康检查、秘密注入、Compose 配置与生产部署的边界。

## 4. Git、提交、分支与 PR 规范

### 4.1 不存在唯一“官方分支命名标准”

**规范事实：** Git 官方文档定义如何创建、列出、跟踪和删除分支，但不规定团队必须使用 `feature/`、`feat/`、Git Flow 或 trunk-based。来源：[git-branch documentation](https://git-scm.com/docs/git-branch)。

因此分支模型属于**项目建议**。本项目是全新脚手架、当前团队规模未知，优先建议较轻的单主干策略：

- 一个受保护的默认分支，建议早期统一为 `main`；若保留 `master` 也可以，但文档、CI 与仓库设置必须一致。
- 短生命周期任务分支，不设置长期 `dev`，除非确有独立集成环境、发布列车或多版本维护需求。
- 分支格式：`<type>/<issue-or-short-slug>`。
- 建议类型：`feat/`、`fix/`、`refactor/`、`docs/`、`test/`、`build/`、`ci/`、`chore/`、`hotfix/`。
- 例：`feat/123-user-import`、`fix/login-lockout`。
- 禁止直接向受保护分支推送、禁止共享分支强推、合并后删除任务分支。

若项目确定保留 `dev`，则必须明确：

- `dev` 是否为所有 PR 的基线；
- `master/main` 何时从 `dev` 发布；
- hotfix 如何回灌；
- 两条分支分别要求哪些检查；
- 谁可以执行发布合并。

没有这些定义时，“同时维护 `dev` 和发布分支”只会增加漂移，并不会自动提升质量。

### 4.2 提交消息

**规范事实：** Conventional Commits 1.0.0 定义的结构是：

```text
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

`fix` 对应修复，`feat` 对应新功能；破坏性变更通过 `!` 或 `BREAKING CHANGE:` footer 表达。规范只强制定义 `feat`、`fix` 和 breaking change 的语义，其他类型可以由项目扩展。来源：[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)。

本项目建议：

- 延续现有 commitlint 类型：`feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`revert`、`chore`。
- `wip` 可以出现在个人分支，但不允许作为合并后保留的最终提交或 squash 后的 PR 标题。
- scope 使用稳定领域名：`backend`、`frontend`、`auth`、`user`、`role`、`menu`、`docker`、`deps`、`ci`、`docs`；不要把文件名当 scope。
- 标题描述“变更结果”，不写“update code”“修复问题”等无信息文本。
- 一个提交只表达一个可审查意图；格式化、依赖升级和业务行为变化尽量分开。
- 行为原因、替代方案、迁移方式放在 body；关联 Issue 和 breaking change 放 footer。

示例：

```text
feat(auth): add lockout after repeated login failures

Persist failed attempts in Redis so limits apply across workers.

Closes #123
```

### 4.3 版本与发布

**规范事实：** SemVer 2.0.0 要求先声明公共 API，然后使用 `MAJOR.MINOR.PATCH`；不兼容 API 变更增加 MAJOR，向后兼容功能增加 MINOR，向后兼容修复增加 PATCH。`0.y.z` 表示初始开发阶段，`1.0.0` 定义公共 API。来源：[Semantic Versioning 2.0.0](https://semver.org/)。

项目建议：

- 先明确这个管理系统的“公共 API”包括哪些内容：HTTP API、环境变量、数据库迁移兼容、插件协议、前端可复用包，不能仅看 Python 包版本。
- 前后端当前各自版本不同（后端 `2.0.0`、前端 `3.0.0`），需要决定是“产品统一版本”还是“组件独立版本”；不要让两个数字在无说明时并存。
- 发布 tag 使用 `vX.Y.Z`，发布说明来自合并 PR，而不是盲目把每条提交都展示给用户。
- 数据库迁移、配置项删除、响应字段变更需要单独标记兼容性和回滚方案。

### 4.4 PR 质量门槛

GitHub 的受保护分支可以要求状态检查、评审、CODEOWNERS 审批、签名提交，并阻止强推或删除；规则集还能统一要求工作流。来源：[GitHub branches and protected branches](https://docs.github.com/en/pull-requests/reference/branches)、[Managing and standardizing pull requests](https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests)。

建议的 PR 模板字段：

```markdown
## 目的

## 变更范围

## 不在本 PR 范围

## 风险与兼容性

## 验证证据

- [ ] backend lint/format/type/test
- [ ] frontend lint/format/type/test/build
- [ ] 数据库迁移升级与回滚（如适用）
- [ ] UI 截图/录屏（如适用）
- [ ] 安全与权限检查（如适用）

## 发布/回滚说明

## 关联 Issue/ADR
```

项目建议的合并条件：

1. PR 描述完整，范围可审查。
2. CI 所有必需检查通过。
3. 至少一名非作者审批；敏感目录需要 CODEOWNER 审批。
4. 新行为有测试，修复缺陷有回归测试。
5. API/配置/数据库/部署行为变化同步文档。
6. 不存在未解释的生成文件、锁文件或大规模格式化变化。
7. 使用 squash merge 时，PR 标题必须符合 Conventional Commits；否则最终历史会绕过单提交校验。

## 5. 代码质量门禁

### 5.1 原则：本地可修复，CI 只验证

当前前端 `pnpm lint` 是变异式命令，会写回文件。后端 Ruff 配置设置了 `fix = true`，直接运行 `ruff check` 也可能修改文件。

**规范事实：** Ruff `format --check` 不写文件，发现未格式化文件时返回非零；Ruff `check` 支持 `--no-fix` 覆盖配置中的自动修复。来源：[Ruff formatter](https://docs.astral.sh/ruff/formatter/)、[Configuring Ruff](https://docs.astral.sh/ruff/configuration/)。

因此建议将命令明确分为两组：

| 用途 | 行为 | 示例 |
| --- | --- | --- |
| `fix` | 开发者主动修复，可改文件 | Ruff `check --fix`、Ruff `format`、Prettier `--write` |
| `check` | CI 与提交前验证，不改文件，失败即非零 | Ruff `check --no-fix`、Ruff `format --check`、Prettier `--check` |

建议的后端门禁：

```bash
cd backend
uv sync --locked
uv run ruff check --no-fix .
uv run ruff format --check .
uv run pytest
```

`uv --locked` 会验证锁文件与项目元数据一致，过期时直接失败而不是更新；这是比 `--frozen` 更合适的 CI 一致性检查。来源：[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)。

建议的前端门禁：

```bash
cd frontend/web
pnpm install --frozen-lockfile
pnpm run lint:check
pnpm run type-check
pnpm run test
pnpm run build
```

其中 `lint:check` 需要单独实现为非变异式命令，不能直接复用当前 `pnpm lint`。本研究不修改脚本，只指出落地要求。

### 5.2 Python 类型检查

本项目后端尚未配置 mypy 或同类工具。

**规范事实：** mypy 官方建议对既有代码从小范围开始，把配置和版本提交到仓库，并尽早加入 CI，确保所有开发者检查同一批文件和相同选项。来源：[Using mypy with an existing codebase](https://mypy.readthedocs.io/en/stable/existing_code.html)。

项目建议：

1. 不要第一天就对整个动态 ORM 代码库开启最严格模式。
2. 第一阶段检查 `app/common`、`app/config`、`app/utils` 中边界清晰的模块，以及新代码。
3. 第二阶段纳入 schema、service；最后处理 ORM/插件动态区域。
4. 所有 `# type: ignore` 必须带具体错误码和原因，禁止无理由全文件忽略。
5. 将 mypy 版本加入 `dependency-groups.dev` 并固定在锁文件，CI 运行仓库统一命令。

### 5.3 前端类型与静态检查

项目建议：

- `vue-tsc --noEmit` 为必需检查；新增 API、store、component props/emits 和表格行数据必须具备类型。
- `any` 只能用于不可控边界，并应尽快通过 `unknown` + narrowing 转换为领域类型。
- ESLint、Prettier、Stylelint 的“写入”和“检查”脚本分离。
- `.vue`、`.ts`、样式、JSON/YAML/Markdown 由各自权威工具处理，避免两个 formatter 争夺同一规则。
- 不允许通过降低全局规则、批量 `eslint-disable` 或 `@ts-ignore` 来让单个 PR 变绿。

### 5.4 pre-commit 与 Husky 的定位

**规范事实：** pre-commit 是多语言 Git hook 管理框架，可在提交前发现格式、调试语句等问题；其官方文档也建议在 CI 中执行，以免本地 hook 被跳过。来源：[pre-commit official documentation](https://pre-commit.com/)。

项目建议有两种可接受方案，二选一，不要叠加两套互相重复的 hook 系统：

- **方案 A（更适合本仓库）：** 根级 `pre-commit` 统一 Python、前端和通用文件检查，commit-msg 继续复用 commitlint。
- **方案 B：** 保留前端 Husky，后端不增加本地 hook，只依赖根级脚本和 CI。

无论选择哪一个，本地 hook 都只是快速反馈，**CI 才是权威门禁**。禁止把耗时很长、依赖数据库或网络的全套集成测试塞进每次 commit；这些应放 pre-push 或 CI。

## 6. 测试策略

### 6.1 官方工具事实

pytest 默认会递归发现 `test_*.py` 或 `*_test.py`，并收集 `test` 前缀的函数/方法；官方建议隔离开发环境，并说明测试布局与导入模式会影响测试是否真正针对安装后的包运行。来源：[pytest good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)。

Vitest 官方支持 V8 或 Istanbul 覆盖率 provider，并可配置覆盖率阈值；覆盖率能力本身不代表项目必须采用某个固定百分比。来源：[Vitest coverage](https://vitest.dev/guide/coverage.html)。

### 6.2 本项目建议的测试分层

| 层级 | 后端 | 前端 | 合并门禁 |
| --- | --- | --- | --- |
| 单元测试 | 纯函数、validator、权限规则、service 分支 | composable、store、utility、组件状态 | 每个 PR 必需 |
| 组件/接口测试 | FastAPI endpoint、鉴权、schema、事务 | Vue component、表单、权限与交互 | 相关改动必需 |
| 集成测试 | 数据库、Redis、迁移、外部适配器 | API client 与 mock server | 相关 PR 或独立 CI job |
| E2E/冒烟 | 登录、权限、关键 CRUD、迁移后启动 | 浏览器关键路径 | 默认分支/发布前 |

硬性建议：

- 修 bug 必须先有能复现旧行为的回归测试，除非有明确、书面的不可测试原因。
- 测试断言业务结果，不以内部调用次数代替业务行为，除非调用协议本身就是合同。
- 单元测试不访问真实网络、生产数据库或共享 Redis。
- 时间、随机数、环境变量和外部服务必须可控制。
- 数据库测试保持隔离，可重复运行，失败后不污染下一用例。
- 权限测试至少覆盖未登录、无权限、有权限三个路径。
- 上传、富文本、SQL、模板、鉴权等敏感功能必须包含负向测试。

### 6.3 覆盖率不要先拍脑袋定 80%

“全仓覆盖率 80%”不是 pytest、Vitest 或 Python 的官方标准。项目建议采用基线递增：

1. 先测量当前后端和前端覆盖率，建立基线。
2. 新增或修改的核心业务代码要求覆盖关键成功、失败和边界路径。
3. 全仓阈值只升不降；需要降低时必须在 PR 中说明原因并获批准。
4. 对鉴权、权限、金额、数据迁移、安全过滤等高风险模块设置更高的局部要求。
5. 不把覆盖率当作唯一质量指标；无意义断言可以提高数字却不能降低风险。

## 7. 依赖、锁文件与构建可复现性

### 7.1 Python

**规范事实：** Python Packaging User Guide 定义 `[dependency-groups]` 可承载 lint、测试等内部开发依赖，并且这些依赖不进入构建后的包元数据。来源：[PyPA Dependency Groups specification](https://packaging.python.org/en/latest/specifications/dependency-groups/)。

本项目已经采用这个结构。建议进一步明确：

- `backend/pyproject.toml` 是直接依赖与工具配置的权威源。
- `backend/uv.lock` 是可复现解析结果，必须提交。
- `backend/requirements.txt` 若生产部署仍需要，应由 `uv export` 生成并在 CI 校验无漂移，不接受手工双写。
- 依赖新增必须说明用途、维护状态、许可证、替代方案、体积与安全影响。
- 运行时依赖和 dev 依赖严格分组；测试工具不进入生产镜像。
- 升级依赖使用独立 PR，附测试与 breaking change 检查，不夹带业务重构。

### 7.2 前端

项目已经在 `package.json` 声明 `packageManager: pnpm@9.15.3`。建议：

- `pnpm-lock.yaml` 是唯一前端锁文件。
- 确认所有环境均使用 pnpm 后，单独 PR 删除 `package-lock.json`，并在 CI 阻止其他锁文件回归。
- CI 使用 `pnpm install --frozen-lockfile`。
- 包管理器主版本通过 Corepack 或 CI action 固定，Node 版本与 `engines` 对齐。
- 依赖升级和 Vite/TypeScript/Vue 主版本迁移分开处理。

## 8. 安全规范与供应链门禁

### 8.1 工具能做什么，不能做什么

**规范事实：** `pip-audit` 检查 Python 环境、项目或锁文件中的已知依赖漏洞；它不是静态代码分析器，也不能保证发现恶意包。来源：[PyPA pip-audit](https://github.com/pypa/pip-audit)。

**规范事实：** Bandit 通过 Python AST 和插件查找常见安全问题，可按严重度与置信度筛选；它同样不能替代威胁建模和人工审查。来源：[Bandit documentation](https://bandit.readthedocs.io/en/latest/man/bandit.html)。

**规范事实：** GitHub dependency review 可在 PR 中展示依赖变化和已知漏洞，并能作为失败检查阻止引入有漏洞的版本；Secret scanning push protection 可在秘密进入仓库前阻止推送。来源：[GitHub dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)、[GitHub push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection)。

### 8.2 建议的安全基线

P0：

- 真实秘密只来自环境变量、Secret Manager 或 CI secrets；仓库只保留 `.env.example` 占位符。
- 启用 GitHub secret scanning/push protection（受仓库类型和套餐支持情况影响）。
- PR 对锁文件变化执行 dependency review。
- 不记录密码、token、cookie、完整 Authorization header、身份证件或其他敏感数据。
- 鉴权、权限、上传、富文本、SQL 执行、代码生成、模板渲染和 AI 工具调用列为高风险目录。

P1：

- 后端 CI 执行 `pip-audit`（以锁文件或已经同步的隔离环境为输入）。
- 前端执行 `pnpm audit`，先设定“新增高危/严重漏洞阻断”，存量问题建账，不用永久 `|| true` 吞掉结果。
- Bandit 首次引入先形成 baseline；新问题阻断，存量逐步清零。
- GitHub Actions 使用最小 `permissions`；第三方 action 选择可信来源，并根据供应链风险决定是否固定到完整 commit SHA。

P2：

- 为认证、权限、数据导出、文件上传、动态 SQL/代码执行、AI 工具权限建立威胁模型。
- 定期恢复测试备份、演练密钥轮换和迁移回滚。
- 发布镜像执行漏洞扫描，生产镜像使用非 root 用户并减少不必要内容。

所有扫描豁免必须记录：漏洞/规则 ID、适用组件、不可利用的证据、责任人、到期日。不能只写“误报”。

## 9. CI 设计

### 9.1 推荐的根级工作流

```text
.github/workflows/
├── ci.yml                 # PR 与默认分支：lint/type/test/build
├── security.yml           # PR 依赖审查 + 定时依赖/代码扫描
├── docker.yml             # Docker 构建与冒烟（相关路径变化时）
└── release.yml            # tag 触发，独立于普通 CI
```

建议 `ci.yml` 的 job：

| Job | 触发路径 | 只读命令/目标 |
| --- | --- | --- |
| `repo-hygiene` | 全部 | 锁文件唯一性、秘密样式、配置/文档基本检查 |
| `backend-quality` | `backend/**` | lock check、Ruff lint、Ruff format、mypy（分阶段） |
| `backend-test` | `backend/**` | pytest + 覆盖率报告 |
| `frontend-quality` | `frontend/web/**` | ESLint/Prettier/Stylelint check、vue-tsc |
| `frontend-test` | `frontend/web/**` | Vitest + 覆盖率报告 |
| `frontend-build` | `frontend/web/**` | production build |
| `docker-build` | Docker/依赖变化 | 镜像构建、健康检查/启动冒烟 |

项目建议：

- PR 门禁必须快且确定，互不依赖的 job 并行运行。
- lint/type/test/build 使用与本地相同的仓库脚本，避免 CI 复制一套命令后漂移。
- CI 不执行自动修复，也不自动提交格式化结果。
- 使用锁文件缓存，但缓存不是依赖事实源。
- 失败日志要足以复现，不能只输出“command failed”。
- 对 README/docs-only 变更可以路径过滤昂贵构建，但通用文档、链接和秘密检查仍应运行。
- 分支保护要求上述关键检查通过后才能合并。

### 9.2 建议的必需检查名称

名称要稳定，否则 GitHub 分支保护会因重命名失去约束：

```text
ci / repo-hygiene
ci / backend-quality
ci / backend-test
ci / frontend-quality
ci / frontend-test
ci / frontend-build
security / dependency-review
```

GitHub 官方说明，required status check 必须在最新提交 SHA 上成功，才能满足保护规则。来源：[Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)。

## 10. 文档治理

### 10.1 文档种类与单一事实源

| 文档 | 回答的问题 | 不应重复的内容 |
| --- | --- | --- |
| `README.md` | 项目是什么、如何最快跑起来 | 完整编码规范、所有运维细节 |
| `AGENTS.md` | 在本目录工作必须遵守什么、去哪里找细节 | 框架教程、长篇架构说明 |
| `ARCHITECTURE.md` | 系统边界、模块和依赖方向 | 每个函数/类清单 |
| `CONTRIBUTING.md` | 人类贡献者如何建环境、分支、提交、提 PR | 业务架构百科 |
| `SECURITY.md` | 如何报告漏洞、支持版本和响应边界 | 内部秘密或可被利用的操作细节 |
| `CHANGELOG.md` | 每个已发布版本对用户可见的变化 | Git log 原样复制 |
| ADR | 为什么做了一个重要且持久的技术决策 | 日常小改动流水账 |
| runbook | 如何部署、回滚和排障 | 设计历史 |

### 10.2 防止文档腐化

项目建议：

- 每份核心文档顶部写 `owner`、`status`、`last-reviewed`。
- 代码改动导致文档事实变化时，文档是同一 PR 的完成条件。
- 架构和 API 文档尽量由代码/Schema 生成；生成文件明确标注“不可手改”。
- 文档链接、命令和目录路径纳入 CI 检查。
- 每季度或每个大版本执行一次文档盘点：删除过期说明，而不是无限追加“注意事项”。
- `AGENTS.md` 只链接当前事实源；出现重复规则时选定一处权威位置，其他位置只链接。

## 11. 推荐的 Definition of Done

每个代码 PR 至少满足：

- [ ] 变更范围与需求一致，没有无关重构或锁文件变化。
- [ ] 已阅读并遵守修改路径适用的所有 `AGENTS.md`。
- [ ] 设计遵循既有模块边界；新增持久性架构决策有 ADR。
- [ ] 新行为有测试，缺陷修复有回归测试，负向/边界路径已考虑。
- [ ] 对应 lint、format check、type check、test、build 全部通过。
- [ ] 没有新增秘密、敏感日志、高危依赖或未解释的安全扫描结果。
- [ ] API、数据库、配置、权限、部署影响已说明并验证兼容/迁移/回滚。
- [ ] 用户可见变化、开发命令或架构事实变化已同步文档。
- [ ] PR 提供可复核证据；未验证项明确说明，不能写成“应该没问题”。
- [ ] 合并标题/提交符合 Conventional Commits，WIP/FIXME 有 Issue 或在合并前清理。

## 12. 分阶段落地顺序

### 阶段 0：先作治理决策

1. 默认分支选择 `main`、`master` 或 `dev`；建议单一 `main`。
2. 明确产品统一版本还是前后端独立版本。
3. 明确 `pyproject.toml`/`uv.lock`/`requirements.txt` 的权威与生成关系。
4. 明确本地 hook 采用根级 pre-commit 还是继续 Husky 为主。

### 阶段 1：P0 门禁（应优先完成）

1. 创建短根 `AGENTS.md`、`backend/AGENTS.md`、`frontend/web/AGENTS.md`。
2. 将 CI 建到根 `.github/workflows/`。
3. 把 `fix` 和 `check` 命令分开。
4. CI 覆盖 Ruff format/lint、pytest、前端 lint/type/test/build。
5. 创建 PR 模板并启用默认分支保护。
6. 统一 CONTRIBUTING、CI 和仓库设置中的目标分支。

### 阶段 2：P1 可靠性与安全

1. 清理双锁文件，定义依赖单一事实源。
2. 渐进引入 mypy。
3. 加 dependency review、pip-audit、pnpm audit、Secret scanning。
4. 创建 `SECURITY.md`、`CODEOWNERS`、测试策略和依赖策略。
5. 建立覆盖率基线与只升不降的规则。

### 阶段 3：P2 可持续治理

1. 写系统架构、数据迁移、运维回滚文档。
2. 引入 ADR 和高风险模块威胁模型。
3. 增加关键路径 E2E、Docker 冒烟和发布门禁。
4. 将文档链接、生成文档漂移、依赖策略等纳入机械检查。

## 13. 建议采用的最小规范集

如果项目当前只有少量开发者，不建议一次性创建几十个空文档。最小而有效的一组是：

```text
AGENTS.md
ARCHITECTURE.md
CONTRIBUTING.md
SECURITY.md
backend/AGENTS.md
frontend/web/AGENTS.md
docs/engineering/code-quality.md
docs/engineering/testing-strategy.md
docs/engineering/git-workflow.md
.github/pull_request_template.md
.github/workflows/ci.yml
```

这组文件解决“如何工作、代码边界、如何贡献、安全报告、局部约束、门禁细节和自动执行”七个关键问题。其余文档等真实复杂度出现后再增加。

## 14. 关键反偏差提醒

1. **写了规范不等于执行了规范。** 没有 CI/分支保护的文字规则只能提供提示，不能形成门禁。
2. **工具更多不等于质量更高。** 先修复现有 CI 路径和变异式 lint，再考虑引入新工具。
3. **覆盖率高不等于测试有效。** 风险路径、边界和断言质量比单一百分比重要。
4. **Conventional Commits 不等于提交天然原子。** 格式正确的巨大提交仍然难审查。
5. **锁文件不等于供应链安全。** 它提高可复现性，但仍需漏洞、许可证、来源和秘密检查。
6. **AGENTS.md 不是架构本身。** 它应该导航到可维护、可验证的事实源。
7. **分层文件不是越多越好。** 只有局部规则确实不同才增加下级文件，否则会制造冲突和腐化。

## 15. 第一方/原始资料索引

### Codex 与仓库指令

- [OpenAI — Introducing Codex](https://openai.com/index/introducing-codex/)
- [OpenAI — Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- [OpenAI — Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)

### Git、提交、版本与 GitHub

- [Git — git-branch documentation](https://git-scm.com/docs/git-branch)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [GitHub — Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub — Workflows](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)
- [GitHub — Branches and protected branches](https://docs.github.com/en/pull-requests/reference/branches)
- [GitHub — Managing and standardizing pull requests](https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests)
- [GitHub — Required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)

### Python 工程质量

- [PyPA — Dependency Groups specification](https://packaging.python.org/en/latest/specifications/dependency-groups/)
- [uv — Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Ruff — Formatter](https://docs.astral.sh/ruff/formatter/)
- [Ruff — Configuration and CLI](https://docs.astral.sh/ruff/configuration/)
- [pytest — Good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [mypy — Using mypy with an existing codebase](https://mypy.readthedocs.io/en/stable/existing_code.html)
- [pre-commit — Official documentation](https://pre-commit.com/)

### 前端与安全

- [Vitest — Coverage](https://vitest.dev/guide/coverage.html)
- [pnpm — audit](https://pnpm.io/cli/audit)
- [PyPA — pip-audit](https://github.com/pypa/pip-audit)
- [Bandit — Official documentation](https://bandit.readthedocs.io/en/latest/man/bandit.html)
- [GitHub — Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)
- [GitHub — Push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection)

---

本文件只提供研究证据和落地建议。只有在项目负责人确认分支模型、版本模型、依赖事实源和 hook 方案，并把相应规则写入正式规范与 CI 后，相关要求才应被视为“项目已生效规范”。
