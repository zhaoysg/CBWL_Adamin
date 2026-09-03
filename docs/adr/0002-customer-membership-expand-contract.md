# ADR-0002：客户身份与会员归属采用 Expand / Migrate / Contract

- 状态：Accepted
- 日期：2026-09-03
- 前置：ADR-0001 管理员与客户身份域分离

## 背景

现有 `cw_member_subscription.user_id` 指向内部系统表 `sys_user.id`。直接把该列重命名或替换为 `customer_id` 会产生不可接受的风险：

- 无法在上线前证明所有历史订阅都能映射；
- 管理员、外部客户和停用账号可能被错误合并；
- 标识冲突可能覆盖已有客户身份；
- Portal 与管理后台若同时发布，容易出现新旧代码不兼容；
- 回滚时可能丢失会员归属。

## 决策

采用三阶段迁移，而不是一次性破坏性迁移。

### 1. Expand

本阶段只增加：

```text
cw_customer_legacy_map
cw_member_subscription.customer_id NULL
```

同时保留：

```text
cw_member_subscription.user_id NOT NULL
```

现有管理端、Portal 和会员权限行为保持不变。

### 2. Migrate

独立迁移任务先执行只读计划并分类：

- `eligible`：无管理员信号、账号有效、标识无冲突，可迁移现有密码哈希；
- `claim_required`：管理员特征、停用状态或无效标识，仅建立客户归属，必须重新认领凭据；
- `identifier_conflict`：客户 realm 已存在同标识，禁止自动合并；
- `already_mapped`：已存在一对一映射，任务幂等跳过。

数据写入按单个历史用户事务化执行：

```text
auth_subject
+ auth_identity（仅 eligible）
+ cw_customer
+ cw_customer_legacy_map
+ 该用户全部 subscription.customer_id 回填
```

任何一步失败则该用户整组回滚。

### 3. Contract

只有当以下门禁全部通过时，才允许进入 Contract：

- 所有非删除订阅的 `customer_id` 均非空；
- 不存在一个旧用户映射多个客户或一个客户映射多个旧用户；
- 冲突清单已人工处理；
- Portal Auth 已完全使用 customer realm；
- 会员查询已双读比对且结果一致；
- 订单支付分支已基于 `customer_id` 回归；
- 回滚演练通过。

随后才会：

- 将 `customer_id` 改为 `NOT NULL`；
- 停止读取 `user_id`；
- 在单独版本中移除旧外键和旧列。

## 安全约束

- 不因邮箱、手机号或用户名相同而跨 realm 自动合并；
- 不自动复制具有超级管理员、部门、角色或岗位信号的账号密码；
- 映射表不保存密码、Token 或完整敏感资料；
- H5 仍只通过 Portal API 访问数据；
- MySQL 是持久化业务数据的唯一运行时数据源。

## 回滚

Expand 迁移不修改历史数据。回滚顺序为：

1. 删除会员表的新客户外键；
2. 删除客户窗口索引；
3. 删除可空 `customer_id`；
4. 删除迁移映射表。

旧 `user_id` 始终保留，因此 Expand 阶段回滚不会丢失会员归属。
