# Web Frontend 开发规范

本文件适用于 `frontend/web/`。它在根目录 [`AGENTS.md`](../../AGENTS.md) 基础上补充 Vue Web 规则。

## 1. 环境与包管理

- Node.js 要求以 `package.json#engines` 为准，当前至少 20.19.0；包管理器以 `packageManager` 为准，当前为 pnpm 9.15.3。
- 只使用 pnpm。当前仓库同时跟踪了 `pnpm-lock.yaml` 和历史 `package-lock.json`；新工作不得运行 `npm install` 或更新 `package-lock.json`。
- 未明确涉及依赖时，不修改 `package.json`、`pnpm-lock.yaml`、`.npmrc` 或构建配置。
- `.env`、`.env.development` 等真实配置不得提交；示例文件只保留安全占位值。浏览器端变量即使以 `VITE_` 注入也不是秘密。
- 所有命令默认在 `frontend/web/` 执行。

## 2. 目录职责

- `src/views/<domain>/`：页面和页面私有组件。
- `src/api/<domain>/`：后端 API 封装与接口类型。
- `src/components/`：有真实跨页面复用价值的组件；业务专用组件留在对应 view。
- `src/hooks/`：可复用组合式逻辑；`src/store/`：Pinia 跨页面状态。
- `src/router/`：路由、守卫与菜单转换；`src/utils/`：无业务归属的稳定工具。
- `src/config/`、`src/plugins/`、`src/layouts/` 属于基础设施层，修改需评估全站影响。

不要为了单一页面创建通用组件、全局 store 或新的请求层。

## 3. Vue 与 TypeScript

- 新代码使用 Vue 3 Composition API 和 TypeScript，遵循相邻组件的 `<script setup>` 风格。
- `tsconfig.json` 已启用 `strict` 和 `noUncheckedIndexedAccess`；不使用 `as any`、`@ts-ignore` 或非空断言掩盖真实问题。
- API 入参、响应、表单模型、表格行、组件 props/emits 都应有明确类型；复用现有全局类型时先确认其实际字段语义。
- props 视为只读；派生值使用 `computed`，副作用使用边界清晰的 `watch`/生命周期函数，并在卸载时清理监听器、计时器和请求。
- 列表渲染使用稳定业务 key；异步交互处理 loading、重复提交、失败反馈和过期响应。
- 大组件按业务职责拆分，不以行数机械拆分；不要把仅使用一次的简单逻辑过度抽象成 hook。

## 4. API、路由与权限

- API 统一通过 `@utils` 导出的 `request` 实例；禁止在页面散落裸 `fetch`、直接 `axios.create` 或第二套拦截器。
- 一个资源使用稳定的 `API_PATH`，HTTP 方法、字段名、分页与响应类型必须和后端一致。
- 上传下载显式处理 `FormData`、`Blob`、文件名、错误响应和资源释放。
- 页面与 API 按相同业务域组织；跨模块引用避免反向依赖和循环依赖。
- 路由 name/path、菜单 component、缓存标识和后端权限码必须同步。前端权限指令只改善体验，不替代服务端授权。
- 修改登录、Token 刷新、路由守卫或请求拦截器时，必须覆盖并发请求、401 循环、退出清理和开放路由。

## 5. UI、可访问性与样式

- 优先复用 Element Plus 和仓库已有 `fa-*` 组件，保持现有设计语言，不在业务任务中进行无关视觉重构。
- 表单必须有标签、校验、提交状态和明确错误反馈；危险操作需要确认与可理解的后果说明。
- 交互元素必须可通过键盘使用，并保留合理焦点、语义标签和必要的 ARIA 信息。
- 样式尽量使用局部作用域和既有变量；禁止无理由使用大范围 `!important`、全局选择器或硬编码层级。
- 响应式行为、空状态、加载态、错误态和长文本是页面验收的一部分。
- 用户可见中文、环境文件和 i18n 资源保持 UTF-8 无 BOM。

## 6. 测试规则

- 单元/组件测试与代码邻近，命名 `*.spec.ts` 或 `*.test.ts`，使用 Vitest 与 Vue Test Utils。
- 测试用户可观察行为，不依赖组件内部实现细节；外部请求、时间和浏览器能力应稳定 mock。
- 修复交互缺陷必须覆盖复现路径；表单、权限、路由和安全组件至少测试关键边界与失败路径。
- 不使用只为通过测试而弱化断言、任意延时或跳过用例的做法。

## 7. 验证命令

```powershell
# 使用现有锁文件安装
pnpm install --frozen-lockfile

# 非修改式质量检查
pnpm exec eslint "src/**/*.{vue,ts,js}"
pnpm exec prettier --check "**/*.{js,cjs,ts,json,tsx,css,less,scss,vue,html,md}"
pnpm exec stylelint "**/*.{css,scss,vue}"
pnpm run type-check

# 测试与构建
pnpm run test
pnpm run build
```

当前 `pnpm run lint` 内含 `--fix`/`--write`，会修改文件；只有在明确需要格式化任务相关文件时才能使用，运行后必须复核 `git diff`，不得提交全仓格式化噪声。

按风险可先运行单文件测试：

```powershell
pnpm exec vitest run src/components/forms/fa-drag-verify/index.spec.ts
```

## 8. 生成文件与构建

- 不手工修改 `src/types/auto-imports.d.ts`、`src/types/components.d.ts`、`.eslintrc-auto-import.json`、`dist/` 或缓存文件。
- Vite alias 变更必须同步 `vite.config.ts`、`tsconfig.json` 以及测试配置；没有必要时不新增 alias。
- 环境变量或 base URL 变化必须同时验证开发模式和目标构建模式，避免只在本地代理下可用。
- 构建成功不代表运行正确；关键页面变化还需验证浏览器控制台、网络请求和主要交互。

## 9. Web Code Review Rules

- 阻止 XSS、不安全 HTML、开放重定向、Token 泄露、仅前端鉴权和敏感数据持久化。
- 阻止 API 方法/字段/响应类型与后端不一致，或通过 `any` 隐藏契约错误。
- 阻止监听器/计时器未清理、重复请求竞态、重复提交和无限重定向。
- 阻止不可操作的键盘交互、缺失表单标签、危险操作无确认，以及只覆盖视觉快照而不验证行为的测试。
