# H5 独立仓库拆分与安全加固方案

> 状态：架构决策已确认，待建立独立仓库后分阶段实施。
> 范围：只定义管理平台与 H5 的边界、迁移顺序和生产安全门禁；本文件不删除旧 H5，也不修改运行代码。

## 1. 架构决策

管理平台与 H5 拆为两个独立 GitHub 仓库、两套构建和发布流程，但继续共用一个后端业务平台和统一数据库。

```text
zhaoysg/CBWL_Adamin
├── backend/              FastAPI、认证授权、Portal API、数据库与业务规则
└── frontend/web/         管理后台

zhaoysg/CBWL_H5
└── Vue 3 H5             用户端页面与 Portal API 客户端
```

部署单元分别为：

```text
admin.example.com         管理后台
api.example.com           FastAPI
m.example.com             H5
```

拆分的是项目、代码仓库、构建、部署和回滚，不拆分后端业务，不复制数据库。

H5 禁止包含：

- 数据库连接或 ORM 模型；
- 管理员 RBAC 与后台菜单逻辑；
- 会员有效期或套餐授权的最终判断；
- 可信价格计算；
- 支付成功判断和订单状态机；
- 第二套用户、商品、会员或订单数据。

## 2. H5 技术基线

独立 H5 直接采用精简的：

- Vue 3；
- TypeScript 严格模式；
- Vite；
- Vant；
- Vue Router；
- Pinia（不持久化 Token）；
- Axios；
- DOMPurify；
- Vitest。

不直接 Fork 完整商城或大而全 H5 模板。`vue3-h5-template`、`vue3-vant-mobile` 等项目只作为工程参考，首版不引入以下非必要能力：

- UniApp 与 APP 条件编译；
- PWA / Service Worker；
- vConsole 或生产 DevTools；
- Pinia 持久化插件；
- 远程 CDN 外置运行时代码；
- Tailwind / UnoCSS 双重样式体系；
- 国际化；
- 文件式路由、复杂自动导入和代码生成；
- 第二套后端或商城业务系统。

## 3. 拆分顺序

### 3.1 建立独立 H5 仓库

1. 创建空仓库 `zhaoysg/CBWL_H5`，初期建议 Private。
2. 不预置 README、License 或 `.gitignore`，避免首次导入冲突。
3. 导入新的 Vue 3 H5 基线。
4. 在可联网的干净环境生成并提交真实 `pnpm-lock.yaml`。
5. 使用冻结安装执行类型检查、测试、生产构建和高危依赖审计。
6. 测试环境联调和独立部署通过后，才进入旧目录清理。

### 3.2 Portal Auth 加固

在本仓库使用独立 PR 新增 `/portal/auth/*`，H5 不再长期调用 `/system/auth/*`。

建议端点：

```text
GET  /api/v1/portal/auth/captcha
POST /api/v1/portal/auth/login
POST /api/v1/portal/auth/refresh
POST /api/v1/portal/auth/logout
```

安全会话模型：

```text
短期 Access Token         只驻留 H5 内存
Refresh Session           HttpOnly + Secure + SameSite Cookie
服务端会话                Redis，可撤销、可轮换、可检测重用
```

Refresh Token/Session 禁止进入：

- localStorage；
- sessionStorage；
- JavaScript 可读 Cookie；
- URL Query、Fragment 或 OAuth 回跳地址；
- 日志、埋点和错误消息。

### 3.3 Portal 数据契约

H5 统一通过 `/api/v1/portal/*` 访问数据。服务端按游客、登录用户、普通会员和指定套餐会员裁剪响应。

权限不足的内容或商品可返回公开预览，但下列字段必须在服务端置空或省略：

- 完整正文；
- 数值价格；
- 真实外部链接；
- 下载地址；
- 内部附件标识；
- 仅授权用户可见的扩展数据。

不能把真实数据完整返回后仅通过 CSS 隐藏。

### 3.4 独立部署与清理旧目录

只有同时满足以下条件，才在单独 PR 中删除 `frontend/app`：

- 新 H5 仓库 CI 全部通过；
- Portal Auth 与预览契约完成；
- 测试环境主要流程联调通过；
- 新 H5 已有独立、可回滚的部署；
- 旧 H5 没有遗漏的业务改动；
- 当前订单支付 Draft PR 的迁移和接口边界不受影响。

清理 PR 再执行：

- 删除 `frontend/app`；
- 删除旧 H5 CI 路径；
- 删除只针对 UniApp/Vite 5 的依赖安全例外；
- 更新根目录仓库地图、工程指南和部署文档；
- 保留迁移说明和 Git 历史引用。

## 4. 当前安全评估

### 4.1 可保留的服务端基础

- Portal 使用可选登录态；
- `public / login / member / premium` 权限矩阵在服务端执行；
- 会员有效期和套餐判定在后端完成；
- Redis 会话具备服务端失效能力；
- 内容发布时已有服务端 HTML 清洗；
- Portal 响应已有 no-store、`Vary: Authorization` 和 nosniff 基础。

这些能力应继续演进，不需要因 H5 拆仓而重写。

### 4.2 生产上线阻断项

#### H-01：浏览器可读取 Refresh Token

当前 UniApp 客户端把 Access Token 与 Refresh Token 写入客户端 Storage。浏览器脚本一旦遭遇 XSS 或不可信第三方脚本，即可能读取长期凭证。

处理：Access Token 只驻留内存；Refresh Session 由后端写入 HttpOnly Cookie。

#### H-02：管理员认证与 H5 认证边界未隔离

当前 H5 使用 `/system/auth/*`，默认 Access/Refresh 有效期均为 12 小时，JWT 载荷没有 Portal 客户端/受众约束。

处理：新增 `/portal/auth/*`、独立 token audience/client、短期 Access Token、Refresh 轮换和重用检测。

#### H-03：登录端点缺少专属限流并可枚举账号

认证控制器已注明登录、OAuth 和验证码缺少更严格的端点级限流；用户不存在和密码错误的公开提示不同。

处理：按 IP、账号标识和会话维度限流；统一公开错误；加入失败退避和安全日志。

#### H-04：当前滑块验证码不能形成有效 Bot 防护

当前流程中，获取 captcha key 后，客户端调用“完成”接口即可把状态改为 verified；服务端没有验证拖动轨迹、签名或第三方挑战证明。

处理：首版改为服务端生成的图片验证码，登录时提交 key 与答案，服务端验证后单次消费；后续可接入服务端验签的专业 Bot Challenge。

#### H-05：Cookie 化后 CORS/CSRF 必须 Fail Closed

当前生产 CORS 域名未配置时会回退到通配 Origin，允许方法和请求头也为通配。切换 Cookie 后不能沿用该配置。

处理：生产启动时强制精确配置 H5/Admin Origin；禁止通配；校验 Origin/Referer、Fetch Metadata 和自定义请求头，高风险写操作增加 CSRF Token 或再次确认。

#### H-06：OAuth 回调不得携带 Token 跳回前端

当前 OAuth 成功回跳会把 Access Token、Refresh Token 和 Token Type 拼入前端 URL。

处理：改为一次性授权码兑换，或直接由服务端设置 HttpOnly Refresh Cookie；前端回调地址必须使用精确白名单。

#### H-07：游客预览必须由服务端裁剪

当前详情正文受服务端权限保护，这是正确基础，但权限不足时整体返回 401/403，尚不支持“游客看预览、登录后看完整内容”。

处理：返回公开元数据、预览正文和访问决策；隐藏字段不进入响应。

### 4.3 中风险项

#### M-01：UniApp/Vite 5 依赖线存在临时安全例外

现有仓库已用精确 GHSA 例外和“不暴露开发服务器”缓解风险；该做法适合作为旧客户端过渡，不适合新 H5 长期基线。

处理：独立 H5 使用已修补的 Vite 8，并继续固定开发服务器只监听 127.0.0.1。

#### M-02：富文本需要双层清洗

服务端 Bleach 清洗继续保留并收窄允许属性；H5 再使用 DOMPurify 二次清洗，禁止 style、表单、iframe、object、SVG/MathML，并校验图片和链接 URL。

#### M-03：安全响应头必须做实际部署验收

Nginx/CDN 必须设置并验证：

- Content-Security-Policy；
- HSTS；
- `frame-ancestors`；
- Referrer-Policy；
- Permissions-Policy；
- X-Content-Type-Options；
- HTML 与哈希静态资源的差异化缓存。

## 5. 商品、价格和链接契约

第一版商品 API 建议：

```text
GET /api/v1/portal/products
GET /api/v1/portal/products/{id}
```

响应按字段授权：

```json
{
  "id": 1001,
  "title": "商品名称",
  "summary": "公开摘要",
  "preview_html": "公开预览",
  "detail_html": null,
  "price": null,
  "action": null,
  "access": {
    "can_view_detail": false,
    "can_view_price": false,
    "can_use_action": false,
    "reason": "login_required",
    "next_action": "login"
  }
}
```

登录且有权限后，后端才返回 `detail_html`、`price` 和 `action`。

外部链接必须满足：

- 仅 HTTPS；
- 精确域名白名单；
- 禁止用户名/密码认证信息；
- 禁止 `javascript:`、`data:` 和协议相对 URL；
- 修改需记录操作人、时间和审计日志；
- 敏感下载使用短时签名地址。

## 6. 质量与安全门禁

H5：

```text
pnpm install --frozen-lockfile
pnpm type-check
pnpm test
pnpm build
pnpm audit --audit-level high
```

后端：

```text
uv run ruff check --no-fix .
uv run ruff format --check .
uv run pytest -q
```

必须补充的验收用例：

1. 游客首页和公开内容正常；
2. 游客响应不存在数值价格、真实链接和隐藏正文；
3. 登录后原路返回并重新加载权限；
4. 失效 Access Token 只触发一次并发刷新；
5. Refresh 重用撤销整条会话链；
6. 退出后服务端和客户端同时失效；
7. 普通用户、过期会员、错误套餐不能越权；
8. OAuth URL 不包含任何 Token；
9. 外链和富文本危险协议被拒绝；
10. 生产构建不包含 Demo、source map、vConsole 或开发配置。

## 7. 与订单支付 PR 的关系

当前 Draft PR #5 聚焦订单、支付事件、会员自动发放、退款和 Outbox。H5 拆分与 Portal Auth 使用独立 PR，不在交易迁移链未稳定时并行删除旧 H5 或增加冲突迁移。

后续 H5 下单仍遵循：

- 客户端不提交可信金额；
- 客户端不自行判定支付成功；
- 支付结果以服务端订单和事件处理结果为准；
- 支付成功后由后端在事务边界内发放会员权益。
