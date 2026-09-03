# 存量会员客户迁移运行手册

## 目标

将仍由 `sys_user.id` 持有的会员订阅，逐步映射到独立的 `cw_customer.id`，同时保留旧 `user_id` 作为回滚路径。

本任务不是 Alembic 数据迁移。Alembic 只负责 Expand 阶段的表和可空列；数据迁移通过显式命令执行并产生审计报告。

## 前置条件

- 已部署 `20260902_01` 身份域迁移；
- 已部署 `20260903_01` 会员归属 Expand 迁移；
- 应用连接的是目标环境 MySQL，不允许 SQLite；
- 操作员拥有受限数据库凭据和安全的报告保存目录；
- 迁移窗口内暂停修改候选用户的后台角色、岗位和会员订阅；
- 已完成数据库备份和恢复演练。

## 第一步：只读计划

默认命令不会修改数据：

```bash
cd backend
uv run python -m app.scripts.migrate_legacy_customers \
  --include-claim-required \
  --report-json /secure/customer-migration-plan.json
```

标准输出只显示数量和 `plan_digest`，不显示用户名、密码哈希或 Token。详细候选信息写入权限为 `0600` 的报告文件。

候选分类：

- `eligible`：可安全复制现有密码哈希到 customer realm；
- `claim_required`：建立客户和会员归属，但不复制登录凭据；
- `identifier_conflict`：客户 realm 已有同标识，禁止自动执行；
- `already_mapped`：已有一对一映射，重跑只修复缺失的 `customer_id`。

## 第二步：审查计划

必须人工确认：

- `identifier_conflict` 全部有处理结论；
- 管理员、部门、角色或岗位账号均未进入 `eligible`；
- 停用账号和无效凭据均进入 `claim_required`；
- 计划中的会员订阅数量与业务报表一致；
- 报告文件没有被复制到代码仓库或公共日志。

## 第三步：显式执行

使用刚生成的摘要；任何数据变化都会使摘要失效：

```bash
uv run python -m app.scripts.migrate_legacy_customers \
  --apply \
  --include-claim-required \
  --plan-digest '<PLAN_DIGEST>' \
  --report-json /secure/customer-migration-apply.json
```

建议先限制到少量用户灰度：

```bash
uv run python -m app.scripts.migrate_legacy_customers \
  --apply \
  --legacy-user-id 123 \
  --plan-digest '<TARGETED_PLAN_DIGEST>' \
  --report-json /secure/customer-123-apply.json
```

每个旧用户使用独立事务：

```text
锁定 sys_user
锁定角色和岗位关联
锁定该用户全部会员订阅
重新分类并检查客户标识冲突
创建 customer identity aggregate 或 claim-required customer
创建一对一映射
回填全部 subscription.customer_id
提交单个用户事务
```

任一步失败时，该用户的主体、身份、客户、映射和订阅回填整体回滚；其他已经成功的用户不受影响。命令只记录错误类型，不向日志输出数据库异常明文。

## 幂等与恢复

- 已有映射时不重复创建 `auth_subject`、`auth_identity` 或 `cw_customer`；
- 如果映射存在但部分订阅的 `customer_id` 为空，重跑会补齐；
- 如果订阅已指向另一个客户，任务拒绝继续并整体回滚；
- 如果映射指向被删除或不存在的客户，任务拒绝继续；
- 数据库唯一约束是并发执行的最终裁决边界。

## 验证 SQL

```sql
SELECT COUNT(*) AS unmapped_subscriptions
FROM cw_member_subscription
WHERE is_deleted = 0
  AND customer_id IS NULL;

SELECT legacy_sys_user_id, COUNT(*) AS mapping_count
FROM cw_customer_legacy_map
WHERE is_deleted = 0
GROUP BY legacy_sys_user_id
HAVING COUNT(*) <> 1;

SELECT customer_id, COUNT(*) AS mapping_count
FROM cw_customer_legacy_map
WHERE is_deleted = 0
GROUP BY customer_id
HAVING COUNT(*) <> 1;

SELECT m.legacy_sys_user_id, m.customer_id, s.id AS subscription_id
FROM cw_customer_legacy_map AS m
JOIN cw_member_subscription AS s
  ON s.user_id = m.legacy_sys_user_id
WHERE m.is_deleted = 0
  AND s.is_deleted = 0
  AND s.customer_id <> m.customer_id;
```

进入 Contract 阶段前，上述异常结果必须全部为空，且 Portal Auth、会员双读、订单支付和回滚演练均已通过。

## 回滚边界

Migrate 阶段不删除 `user_id`。业务回滚可以立即恢复旧版应用继续读取 `user_id`。

不要直接删除已创建的客户或映射。若确需撤销某个迁移，必须在维护窗口内通过专用补偿任务完成，并先确认该客户没有新订单、登录身份、收藏或其他业务数据。数据库结构回滚仅适用于尚未执行任何数据迁移的环境。
