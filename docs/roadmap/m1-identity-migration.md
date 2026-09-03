# M1 身份域实施与迁移计划

## 本批次范围

新增：

- `auth_subject`
- `auth_identity`
- `sys_admin_account`
- `cw_customer`
- 规范化、模型、事务型创建服务和契约测试

本批次不修改：

- `cw_member_subscription.user_id`
- `cw_order.user_id`
- Portal Auth 的现有登录查询
- 管理后台 RBAC 表

这是有意的分阶段策略，确保新增迁移可以无数据损失回滚。

## 迁移链约束

M1 revision：

```text
20260823_01 -> 20260902_01
```

当前订单支付 Draft 的 `20260827_01` 同样从 `20260823_01` 出发。合并顺序必须调整为：

```text
20260823_01 -> 20260902_01 -> 重新编号后的 billing revision
```

禁止让两条 revision 同时进入主干形成 Alembic 多头。订单支付 PR 需要 rebase，并重新
运行 MySQL 升级—回滚—再升级及交易对抗测试。

## 回填步骤

1. 对现有 `sys_user` 分类，明确内部管理员和历史 H5 测试用户。
2. 为内部管理员创建 admin subject / identity / admin account bridge。
3. 为外部用户创建 customer subject / identity / customer。
4. 保存 `legacy_sys_user_id -> customer_id` 映射表或受审计的迁移报告。
5. 手机号、邮箱和用户名冲突必须人工处置，不自动合并跨 realm 身份。
6. 会员订阅、订单和支付事件的可映射率必须达到 100%。

## M2 前置门禁

- 身份表迁移在 MySQL 8.4 升级、回滚和再升级均通过。
- realm/provider/identifier 并发唯一约束测试通过。
- 管理员与客户 Token 跨端拒绝测试通过。
- 会员与订单存量 `user_id` 均有唯一 customer 映射。
- 回滚时不存在只关联新 customer 而无法恢复的业务记录。
