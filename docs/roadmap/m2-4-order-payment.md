# 财不外露 M2.4：订单、支付与会员自动发放

## 1. 背景

M1、M2.2、M2.3 已经完成以下生产基线：

- 管理后台、Portal 契约与 uni-app 用户端；
- 内容分类、投研内容生命周期和会员套餐；
- 真实会员订阅实例、服务端权益判定和数据库 Portal；
- SQLite、MySQL 8.4、PostgreSQL 16 可逆迁移门禁；
- 管理端与用户端构建、类型检查和完整依赖审计。

目前会员权益只能由后台人工授予。M2.4 的目标是建立“用户下单 → 支付事件 → 服务端确认 → 自动发放订阅 → 退款/异常处理”的交易闭环。

## 2. 目标与非目标

### 2.1 本阶段目标

1. 服务端成为价格、订单状态、支付结果和会员发放的唯一权威来源。
2. 外部回调、客户端重试和后台补单均具备幂等性。
3. 支付成功和会员订阅创建在同一业务事务内完成，避免“已付款但无权益”。
4. 支付事件保留可审计证据，同时不记录密钥、完整卡号或无必要的个人敏感信息。
5. 订单、支付、退款和订阅之间具有明确状态机、并发控制与恢复路径。
6. 首先交付 Provider 无关的领域核心和可自动测试的 sandbox/manual Provider，再接真实支付渠道。

### 2.2 非目标

- 本阶段不实现营销优惠券、积分、分账、发票、自动续费和复杂税务。
- 不在客户端保存支付密钥或自行判断付款成功。
- 不把支付渠道的原始状态直接作为内部订单状态使用。
- 不允许通过人工修改数据库来补发权益；所有补单必须走受审计的服务接口。

## 3. 领域模型

所有金额使用整数最小货币单位，例如人民币分；禁止使用浮点数参与金额计算。

### 3.1 `cw_order`

订单聚合根，建议字段：

- `order_no`：服务端生成，全局唯一；
- `user_id`：下单用户；
- `plan_id`：关联会员套餐；
- `plan_snapshot`：下单时的套餐名称、权益、有效期快照；
- `amount_minor`、`currency`：应付金额与币种；
- `status`：`pending / paid / closed / refunding / partially_refunded / refunded / failed`；
- `expires_at`、`paid_at`、`closed_at`；
- `paid_amount_minor`、`refunded_amount_minor`；
- `version_no`：乐观锁；
- 通用创建、更新和软删除审计字段。

约束：

- 订单创建后，套餐价格变化不能影响订单快照；
- `paid_amount_minor <= amount_minor`；
- `refunded_amount_minor <= paid_amount_minor`；
- 已支付订单不能被普通删除；
- 仅 `pending` 订单允许超时关闭。

### 3.2 `cw_payment_attempt`

一次向支付 Provider 发起的支付尝试：

- `attempt_no`、`order_id`；
- `provider`：首阶段 `sandbox / manual`，后续扩展真实渠道；
- `idempotency_key`：同一订单同一业务动作唯一；
- `provider_transaction_id`；
- `status`：`created / pending / succeeded / failed / expired / cancelled`；
- 请求金额、币种和 Provider 返回的可公开状态；
- `failure_code`、经脱敏的 `failure_message`；
- `version_no`。

### 3.3 `cw_payment_event`

外部回调和主动查询结果的不可变事件记录：

- `provider`、`provider_event_id`：联合唯一；
- `event_type`、`provider_transaction_id`、`order_no`；
- `payload_hash`、`signature_verified`、`received_at`；
- `processing_status`：`received / processed / ignored / rejected / failed`；
- `processing_error`：脱敏错误摘要；
- 原始报文仅在确有合规需求时加密保存，并设置保留周期。

重复事件必须返回成功确认，但不能重复改变订单或重复发放会员。

### 3.4 `cw_refund`

- `refund_no`、`order_id`、`payment_attempt_id`；
- `provider_refund_id`、`idempotency_key`；
- `amount_minor`、`reason`；
- `status`：`requested / processing / succeeded / failed / cancelled`；
- `requested_by`、`version_no`；
- 退款事件与订单累计退款金额保持一致。

### 3.5 事务发件箱

建议增加 `cw_outbox_event`，用于在数据库事务提交后可靠触发通知、对账或异步任务，避免在事务内直接调用外部服务。

## 4. 状态机

### 4.1 订单

```text
pending ──支付成功──> paid
   │                   │
   ├──超时/取消──> closed
   │                   ├──申请退款──> refunding
   └──不可恢复错误──> failed           │
                                       ├──部分退款──> partially_refunded
                                       └──全额退款──> refunded
```

状态转换必须使用条件更新或行锁，并同时检查 `version_no`。

### 4.2 支付尝试

```text
created -> pending -> succeeded
                 ├-> failed
                 ├-> expired
                 └-> cancelled
```

一个订单可以有多次失败尝试，但只能有一个成功支付事实；数据库唯一约束和服务层事务共同保证。

### 4.3 会员发放

支付事件满足以下全部条件时才允许发放：

1. 回调签名、时间戳和重放窗口验证通过；
2. Provider 商户身份与配置一致；
3. 订单号存在且状态允许转换；
4. 回调金额和币种与订单快照完全一致；
5. Provider 交易号未绑定到其他订单；
6. 支付事件未被成功处理；
7. 订单更新与 `cw_member_subscription` 创建在同一数据库事务中完成。

订阅的来源建议为 `payment`，`source_ref` 使用稳定的订单号或支付交易号，复用 M2.3 的幂等约束。

退款后的权益回收策略必须显式配置：

- 全额退款：撤销由该订单产生的未到期订阅；
- 部分退款：首阶段不自动缩短权益，进入人工审核；
- 已消费或特殊合同订单：按策略进入异常队列，不静默越权处理。

## 5. API 契约

### 5.1 用户端

- `POST /portal/orders`：按当前启用套餐创建订单；客户端只提交 `plan_id`，金额由服务端读取；
- `GET /portal/orders`：当前用户订单列表；
- `GET /portal/orders/{order_no}`：订单与支付状态；
- `POST /portal/orders/{order_no}/payment-attempts`：创建支付尝试；
- `POST /portal/orders/{order_no}/cancel`：取消未支付订单；
- `GET /portal/orders/{order_no}/payment-result`：受控轮询支付结果。

### 5.2 Provider 回调

- `POST /payments/{provider}/webhook`：读取原始请求体后验签；
- 请求体大小、Content-Type、时间戳和来源配置必须受限；
- 验签失败返回明确非成功响应，但日志不得包含密钥；
- 重复有效通知返回 Provider 要求的成功确认。

### 5.3 管理端

- 订单分页、详情和状态筛选；
- 支付尝试与支付事件审计；
- 受权限控制的人工补单；
- 退款申请、结果查询和异常重试；
- 对账差异列表；
- 所有写操作接入 `OperationLogRoute`。

## 6. Provider 抽象

定义稳定接口，领域服务不得依赖具体 SDK：

```python
class PaymentProvider(Protocol):
    async def create_payment(self, request: CreatePaymentRequest) -> CreatePaymentResult: ...
    async def verify_webhook(self, headers: Mapping[str, str], raw_body: bytes) -> VerifiedPaymentEvent: ...
    async def query_payment(self, provider_transaction_id: str) -> PaymentQueryResult: ...
    async def create_refund(self, request: CreateRefundRequest) -> RefundResult: ...
    async def query_refund(self, provider_refund_id: str) -> RefundQueryResult: ...
```

第一阶段使用确定性的 sandbox Provider 覆盖成功、失败、重复通知、乱序通知和退款。真实渠道适配器作为后续小 PR 接入，不改变领域状态机。

## 7. 安全边界

- Provider 密钥只能从环境变量或密钥管理服务读取；
- 使用原始字节验签，禁止先解析 JSON 再重建报文；
- 比较签名时使用常量时间函数；
- 校验时间戳和 nonce，限制重放窗口；
- 对 webhook 设置独立速率限制、请求体上限和超时；
- 日志对 token、签名、用户标识和原始报文执行脱敏；
- 管理端补单、退款和重试必须分配独立 RBAC 权限；
- 订单详情只允许订单所属用户或管理权限读取；
- 不存在和无权读取的订单统一资源隐藏策略；
- 任何客户端传入的金额、币种、会员有效期均不得直接采用。

## 8. 数据库与并发测试矩阵

必须覆盖：

- 相同幂等键重复下单；
- 相同 Provider 事件并发到达；
- 两个不同事件同时宣告同一订单支付成功；
- 回调金额或币种不匹配；
- 已关闭订单收到迟到支付事件；
- 支付成功事务中订阅创建失败后的整体回滚；
- 支付成功后相同事件重试不重复发放；
- 退款和支付成功事件乱序；
- 退款重复回调；
- 订单 `version_no` 冲突；
- SQLite、MySQL 和 PostgreSQL 的唯一约束与事务行为一致。

## 9. 前端交付

### 9.1 用户端

- 套餐详情与确认订单；
- 支付发起、处理中、成功、失败、已关闭页面；
- 订单历史和详情；
- 支付成功后刷新真实会员权益；
- App/H5 生命周期恢复时重新查询服务端状态，不相信本地成功标记。

### 9.2 管理端

- 订单列表与详情抽屉；
- 支付事件时间线；
- 退款表单和二次确认；
- 异常订单、金额不一致和未发放权益告警；
- 权限按钮与菜单种子。

## 10. CI 质量门禁

M2.4 工作流至少包含：

- Python compileall；
- Ruff lint 与 format check；
- Bandit；
- 订单、支付、回调、退款、幂等、并发和权限测试；
- 应用健康检查；
- SQLite、MySQL 8.4、PostgreSQL 16 迁移往返；
- 管理端冻结安装、类型检查、生产构建和完整依赖审计；
- 用户端冻结安装、类型检查、生产 H5 构建和完整依赖审计；
- webhook 签名测试向量和秘密模式扫描。

CI 预处理应把后端 uv 锁文件迁移到稳定的官方 PyPI 源，消除当前镜像偶发 403；不能通过忽略安装失败来放行。

## 11. 实施顺序

1. **契约与迁移**：模型、状态枚举、可逆迁移、数据库约束；
2. **领域服务**：订单状态机、金额校验、幂等和事务发放；
3. **Sandbox Provider**：支付、回调、查询和退款测试实现；
4. **API 与 RBAC**：Portal、webhook、管理端接口和菜单；
5. **管理端页面**：订单、支付事件、退款和异常处理；
6. **用户端页面**：下单、支付结果和订单历史；
7. **对抗加固**：并发、重放、乱序、金额不匹配和回滚测试；
8. **跨数据库与供应链**：全量 CI 通过后解除 Draft。

## 12. Definition of Done

- [ ] 订单价格完全来自服务端套餐快照；
- [ ] 重复下单、重复回调和重复退款不会产生重复副作用；
- [ ] 支付成功与会员订阅创建具有原子性；
- [ ] 退款策略可审计且不会误撤销其他来源的订阅；
- [ ] 所有敏感管理操作具备独立权限和操作日志；
- [ ] 三种数据库迁移往返成功；
- [ ] 管理端和用户端形成可操作闭环；
- [ ] 完整依赖图无未接受的高危漏洞；
- [ ] Draft PR 描述包含明确边界、测试结果和回滚方式。

## 13. 后续阶段

M2.4 完成后按以下顺序推进：

1. **M2.5 对象存储与媒体资产**：签名上传、素材库、私有资源访问和生命周期；
2. **M2.6 发布准备**：浏览器 E2E、部署基线、可观测性、备份恢复和发布手册；
3. **M3.0 互动与课程域**：收藏、点赞、评论、课程和学习进度。
