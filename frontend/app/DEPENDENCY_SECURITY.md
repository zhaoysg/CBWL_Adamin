# H5 依赖安全策略

最后更新：2026-08-26

## 目标

H5 构建必须使用已提交的 `pnpm-lock.yaml`、固定的 pnpm 版本和完整依赖图审计。高危及严重漏洞默认阻断 CI；任何例外必须精确到单个 GHSA，并记录适用条件、缓解措施和退出条件。

## 已实施的安全版本下限

当前 DCloud uni-app 编译器会引入若干旧的传递依赖。项目通过 `package.json` 中的 `pnpm.overrides` 仅提升实际受漏洞影响的依赖：

- `@intlify/core-base`：低于 `9.1.11` 的版本提升至 `9.1.11`
- `@intlify/message-resolver`：低于 `9.1.11` 的版本提升至 `9.1.11`
- `adm-zip`：低于 `0.6.0` 的版本提升至 `0.6.0`
- `path-to-regexp`：低于 `0.1.13` 的版本提升至 `0.1.13`
- `postcss`：低于 `8.5.25` 的版本提升至 `8.5.26`

未受当前审计问题影响的同族包保持上游解析版本，避免扩大兼容性变更。每次依赖变更都必须通过冻结安装、Vue/TypeScript 类型检查、H5 production 构建和 `pnpm audit --audit-level high`。

## 临时例外：GHSA-fx2h-pf6j-xcff

该例外仅适用于 DCloud 稳定编译器链锁定的 Vite 5。上游修复版本从 Vite `6.4.3` 开始，而当前 DCloud 稳定发布线仍以 Vite 5 为编译基线；直接跨主版本覆盖会脱离上游支持边界，因此暂不强制升级。

风险限定如下：

- 漏洞位于 Vite 开发服务器的 Windows 路径访问处理，不影响已构建的静态 H5 产物本身。
- 生产环境只部署 `uni build` 生成的静态文件，不运行或暴露 Vite 开发服务器。
- CI 在 Ubuntu 上执行 production 构建，不启动网络可访问的开发服务器。
- 开发环境不得使用 `--host` 或 `server.host` 将当前 Vite 开发服务器暴露到不受信任网络。
- `auditConfig.ignoreGhsas` 只允许包含 `GHSA-fx2h-pf6j-xcff`，不允许使用包级、严重度级或通配符豁免。

## 已验证基线

锁文件由 GitHub Actions 在干净 Ubuntu Runner 中使用 Node.js `22.16.0` 与 pnpm `9.15.3` 再生成。提交 `6a09df1e6e048ccba72755246c0e7ef447113435` 已完成：

- 锁文件再生成
- `pnpm install --frozen-lockfile`
- Vue / TypeScript 类型检查
- H5 production 构建
- `pnpm audit --audit-level high`

一次性锁文件修复工作流在完成验证后已删除；后续仅保留正式 M2.3 CI 的冻结安装、构建和审计闸门。

## 退出条件

当 DCloud 稳定发布线正式支持包含该修复的 Vite 主版本后，必须在同一变更中完成以下事项：

1. 升级 DCloud/uni-app 编译器链；
2. 删除 `GHSA-fx2h-pf6j-xcff` 例外；
3. 重新生成锁文件；
4. 通过 H5 类型检查、production/acceptance 构建和完整依赖审计。
