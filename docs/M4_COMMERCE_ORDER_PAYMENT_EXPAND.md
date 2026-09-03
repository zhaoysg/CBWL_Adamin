# M4 Commerce：订单与支付双归属 Expand

## 目的

本阶段建立订单与支付的最小持久化基线，但不接入真实第三方支付，也不在回调到达时直接发放会员。

关键约束：

- 订单价格、币种、有效期和权益全部从服务端会员套餐生成快照；
- 客户端只提供套餐 ID 和幂等请求键，不能提交可信价格；
- 迁移期同时允许 `legacy_user_id` 与 `customer_id`；
- 客户主体同时携带两侧 ID 时，服务会在同一数据库事务内校验一对一迁移映射；
- 订单、支付尝试和提供方事件分别由数据库唯一约束仲裁并发幂等；
- 提供方原始回调载荷不持久化，仅保存 SHA-256 摘要；
- Commerce 表在 MySQL 使用 `utf8mb4_bin`，避免大小写不同的提供方事件号被错误去重；
- 本阶段收到 `payment_succeeded` 事件后仍保持订单与支付为 `pending`，防止未经结算事务就提前发放权益。

## 表

### `cw_commerce_order`

保存不可变订单编号、服务端幂等摘要、客户双归属和会员套餐快照。

归属约束：

```text
legacy_user_id IS NOT NULL OR customer_id IS NOT NULL
```

迁移客户正常写入两列；旧兼容用户只写 `legacy_user_id`；最终 Contract 后允许只写 `customer_id`。

### `cw_payment_attempt`

一次订单可以有多次支付尝试。每次尝试复制订单归属、金额和币种，并通过复合外键保证 `order_id` 与 `order_no` 指向同一订单。

### `cw_payment_event`

按 `(provider, provider_event_id)` 去重第三方回调，只保存规范化事件类型与载荷摘要。复合外键保证 `payment_id` 与 `payment_no` 指向同一支付尝试。

## 幂等边界

订单幂等摘要：

```text
SHA256("membership-order" + owner namespace + request_key)
```

支付尝试幂等摘要：

```text
SHA256("payment-attempt" + owner namespace + request_key)
```

唯一键冲突发生在并发请求时，失败方回滚到 savepoint，再读取胜出的记录。只有所有业务参数一致时才返回已有记录，否则返回 409。

## 事务边界

服务不调用 `commit()` 或 `rollback()`。HTTP 请求或任务处理器负责外层事务；服务只在并发唯一键竞争处使用 `begin_nested()`。

当前实现包含：

- 幂等创建会员订单；
- 乐观锁取消待支付订单；
- 幂等创建支付尝试；
- 幂等登记提供方事件。

当前实现不包含：

- 微信支付或支付宝 SDK；
- 回调签名验证；
- 支付成功状态机；
- 会员订阅发放；
- Outbox 投递；
- 退款与对账。

这些能力必须在后续堆叠 PR 中完成，且支付状态、订单状态、会员订阅和 Outbox 必须在一个数据库事务内提交。

## 回滚

迁移 `20260903_02` 只新增三张 Commerce 表。降级到 `20260903_01` 会按依赖逆序删除：

```text
cw_payment_event
cw_payment_attempt
cw_commerce_order
```

身份、客户映射、会员套餐和会员订阅表不受影响。
