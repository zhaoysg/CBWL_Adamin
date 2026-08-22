# 财不外露 M1

本分支把现有 FastApiAdmin 后台升级为“财不外露”会员投研平台的第一阶段骨架。

## 架构

```text
FastApiAdmin 管理后台（Vue3）
          │
          ▼
FastAPI /api/v1
          │
 ┌────────┼────────┐
 ▼        ▼        ▼
会员      内容      学院
          │
          ▼
uni-app 用户端
 ├─ H5
 ├─ iOS
 └─ Android
```

## 本阶段已增加

- 管理后台品牌名称：财不外露管理平台。
- Portal API：`/portal/home`、`/portal/academy`、`/portal/profile`、`/portal/health`。
- uni-app 用户端：首页、学院、我的三大主页面，一套源码面向 H5 / iOS / Android。
- MySQL 业务模型：会员套餐与订阅、内容分类、内容、互动、评论、课程、章节、课时、学习进度。
- 保留 FastApiAdmin 原有用户、RBAC、菜单、日志、文件、代码生成等能力。

## M1 数据策略

当前 PortalService 使用确定性演示数据，目的是先锁定用户原型、API 合约和三端工程结构。下一阶段把同一 API 切换到 SQLAlchemy Repository，不需要重写 H5 / iOS / Android 页面。

## 本地启动

后端继续按原项目方式：

```bash
cd backend
uv sync
uv run main.py run --env=dev
```

用户端：

```bash
cd frontend/app
pnpm install
pnpm run dev:h5
```

管理后台：

```bash
cd frontend/web
pnpm install
pnpm run dev
```

## 下一阶段

1. PortalService 接 SQLAlchemy 实体和真实数据库；
2. 后台增加“会员中心 / 投研内容 / 投研学院”菜单与 CRUD；
3. 手机号、微信、Apple 登录；
4. 支付、订阅续费和权益校验；
5. MinIO/S3 文件、PDF、视频、直播与回放；
6. iOS/Android 推送、隐私清单、签名与商店构建。

> 上游 FastApiAdmin 使用 MIT License，二次开发继续保留原 LICENSE 和版权声明。
