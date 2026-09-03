# M4 Commerce：订单与支付事实基线

## 目标

本阶段建立唯一、可回滚的订单与支付聚合，为后续 Portal 控制器、支付适配器、会员发放和 Outbox 事务编排提供稳定底座。M4 不接入真实微信/支付宝 SDK，也不直接创建会员订阅。

## Canonical 数据模型

### `cw_order`

保存服务端生成的订单号、客户双归属、会员套餐快照、应付金额、币种、支付截止时间和乐观锁版本。

客户端下单只提交：

```text
plan_id
idempotency_key
```

`unit_price`、`total_amount`、`currency`、套餐名称、套餐编码和有效天数全部由服务端从启用中的 `cw_member_plan` 生成快照。

归属约束：

```text
legacy_user_id IS NOT NULL OR customer_id IS NOT NULL
```

迁移客户写入两列；尚未建立客户映射的兼容用户只写 `legacy_user_id`。一旦旧账号存在有效 `migrated` 映射，legacy 会话不得再创建 legacy-only 新订单。

### `cw_payment_attempt`

保存一次固定订单金额的支付尝试。金额和币种从订单复制，不接受客户端覆盖。服务通过订单行锁保证同一订单同时最多存在一个 `created` 或 `processing` 尝试；失败或关闭后可使用新的幂等键创建下一次尝试。

### `cw_payment_event`

按 `(provider, provider_event_id)` 去重已经完成签名验证的规范化回调。仅保存稳定字段和 `payload_digest`，不保存原始报文、签名、Authorization、Token 或 Cookie。

## 身份与归属

客户会话执行交易前必须同时满足：

1. `cw_customer` 为 active、customer realm、未删除；
2. 对应 `auth_subject` 为 active、customer realm、未删除；
3. `cw_customer_legacy_map` 中存在匹配 legacy/customer 的 `migrated` 映射；
4. 订单上的 `legacy_user_id`、`customer_id` 与当前主体一致。

越权查询统一按订单不存在处理；同一 customer 下出现 legacy 归属不一致时返回服务不可用，防止在迁移数据异常时继续写入财务事实。

## 幂等与并发

- 订单由全局 `idempotency_key` 唯一约束仲裁；
- 支付尝试由 `(order_id, idempotency_key)` 唯一约束仲裁；
- 支付事件由 `(provider, provider_event_id)` 唯一约束仲裁；
- 同一个幂等键只有业务参数完全一致时才返回已有结果，否则返回 409；
- 唯一键竞争只回滚到 savepoint，服务不调用外层 `commit()` 或 `rollback()`；
- 支付路径统一按 `order -> payment_attempt` 获取行锁，避免创建支付与回调处理形成相反锁序；
- 支付事件插入和被接受的订单/支付状态更新在同一个 savepoint 内 flush，任何唯一键或状态约束失败都不会留下半个事件，也不会污染调用方事务。

## 支付状态判定

签名必须由上游 provider adapter 验证后，才能构造 `VerifiedPaymentEventSchema`。

`payment_succeeded` 只有在以下条件全部成立时才被接受：

- 回调金额与支付尝试金额一致；
- 币种一致；
- 订单仍为 pending；
- 支付尝试仍为 created 或 processing；
- provider 的 `occurred_at` 早于订单和尝试截止时间。

判定使用 `occurred_at` 而不是系统收到回调的时间。因此事件在截止前真实发生、但网络延迟导致截止后送达时，仍可被正确接受。支付成功后订单变为 paid、尝试变为 succeeded；本阶段仍不创建会员订阅。

## MySQL 约束

三张表均使用：

```text
ENGINE=InnoDB
CHARSET=utf8mb4
COLLATE=utf8mb4_bin
```

外键不声明级联 referential action，保持默认 RESTRICT/NO ACTION 语义。这样既避免修改历史交易主键，也兼容 MySQL 8.4 对“CHECK 所用列不得参与外键 referential action”的限制。

## 回滚

迁移 `20260903_02` 只新增三张 Commerce 表。降级到 `20260903_01` 按依赖逆序删除：

```text
cw_payment_event
cw_payment_attempt
cw_order
```

客户、身份映射、会员套餐和会员订阅表不受影响。CI 会在真实 MySQL 8.4 上执行 upgrade、业务验证、单 revision downgrade 和 re-upgrade。

## 后续阶段

M4 之后再增加：

- Portal 订单/支付控制器；
- 微信与支付宝签名适配器；
- 会员订阅发放；
- Outbox 与可靠投递；
- 退款、对账和人工补偿。

会员发放与 Outbox 必须和最终支付结算状态在同一数据库事务中提交。
