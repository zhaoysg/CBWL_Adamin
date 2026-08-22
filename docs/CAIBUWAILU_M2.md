# 财不外露 M2：可交互会员端

## 本阶段交付

- 统一 H5 / iOS / Android 的 uni-app 用户端工程升级为 `0.2.0`。
- 按现有原型高还原首页、投研学院、个人中心三大主页面。
- 新增投研内容详情、课程详情、会员中心三个可交互页面。
- Portal API 新增内容详情、课程详情、会员套餐接口。
- 开发环境提供确定性演示数据模式，便于在后端数据库尚未接入时进行视觉验收。
- 新增 Portal API 合约测试，以及移动端 H5 类型检查与构建 CI。

## 当前用户端接口

```text
GET /api/v1/portal/health
GET /api/v1/portal/home
GET /api/v1/portal/academy
GET /api/v1/portal/profile
GET /api/v1/portal/content/{content_id}
GET /api/v1/portal/course/{course_id}
GET /api/v1/portal/member-center
```

## 本地启动

### 后端

```bash
cd backend
cp env/.env.example env/.env.dev
uv sync
uv run main.py run --env=dev
```

### H5

```bash
cd frontend/app
corepack enable
pnpm install
pnpm run dev:h5
```

默认 H5 开发端口为 `5174`。开发环境可通过 `.env.development` 的 `VITE_USE_MOCK` 控制是否使用演示数据；正式环境通过 `/api/v1` 调用 FastAPI。

## 多端构建

```bash
pnpm run build:h5
pnpm run build:app-android
pnpm run build:app-ios
```

页面、API 类型和业务交互由同一套 Vue 3 / uni-app 源码维护；Android 与 iOS 后续仅处理签名、推送、支付、系统权限和应用商店配置等平台差异。

## 数据阶段说明

M2 仍采用服务内确定性 Read Model，用于固定 UI、API 合约和交互路径。M3 将把以下能力接入 SQLAlchemy 与管理后台 CRUD：

1. 会员套餐、订阅与权益；
2. 内容分类、文章、评论、点赞、收藏；
3. 专栏、课程、章节、课时与学习进度；
4. 首页推荐位、排序与发布流程；
5. 用户登录态、支付回调和服务端权限校验。

## 当前边界

- M2 的“确认方案”“预约直播”“继续学习”等按钮已经具备交互入口，但尚未连接真实支付、直播和视频播放服务。
- iOS / Android 共用工程与构建脚本已经建立，真机签名与商店包需要在 Apple / Android 构建环境中继续验证。
- 所有会员内容权限必须最终在 FastAPI 服务端校验，不能只依赖前端隐藏。
