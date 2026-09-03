# Portal 客户身份与会员权益切换手册

## 目标

把 H5 从 `sys_user` 兼容身份平稳切换到 `cw_customer`，同时确保客户会员权限不会因部分回填而误授予或误收回。

身份认证和权益读取使用两个独立开关：

```text
PORTAL_IDENTITY_MODE=legacy|dual|customer
PORTAL_ENTITLEMENT_MODE=legacy|dual|customer
```

默认均为 `legacy`，部署新代码不会自动切换生产行为。

## 模式语义

### 身份模式

- `legacy`：只接受旧 `sys_user` H5 会话；
- `dual`：已迁移账号优先 customer realm，未映射账号才允许旧登录；
- `customer`：只接受 customer realm。

### 权益模式

- `legacy`：按 `cw_member_subscription.user_id` 读取；
- `dual`：迁移客户同时按 `user_id` 和 `customer_id` 查询，要求活动订阅 ID 集合完全一致；
- `customer`：只按 `customer_id` 读取。

双读不一致时接口返回 503 并记录 legacy/customer 主体 ID 和订阅 ID，不返回受限内容，也不静默回退到其中一侧。

## 允许的生产组合

| 身份 | 权益 | 用途 |
|---|---|---|
| legacy | legacy | 初始状态和快速回滚 |
| dual | legacy | 先验证客户登录，不改权益来源 |
| dual | dual | 验证迁移数据一致性 |
| dual | customer | 权益先切客户列，仍保留未映射旧登录但其会员接口失败关闭 |
| customer | customer | 最终客户模式 |

禁止：

- `legacy + customer`：旧会话没有客户主体；
- `customer + legacy/dual`：最终客户模式不能继续依赖旧归属。

生产启动门禁会拒绝上述错误组合。

## 推荐上线顺序

### 0. 结构与迁移准备

- 合并身份域、Expand 和 Migrate 堆叠 PR；
- 在验收 MySQL 执行 Alembic upgrade；
- 运行存量客户 dry-run；
- 处理全部 `identifier_conflict`；
- 灰度执行迁移并复核私有审计报告。

### 1. 认证双读

```dotenv
PORTAL_IDENTITY_MODE=dual
PORTAL_ENTITLEMENT_MODE=legacy
```

观察：

- customer 登录成功率；
- claim-required 数量；
- 旧用户回退数量；
- 客户停用后 Access/Refresh 失效率；
- 管理端与 Portal 跨 Token 拒绝率。

### 2. 权益双读

```dotenv
PORTAL_IDENTITY_MODE=dual
PORTAL_ENTITLEMENT_MODE=dual
```

只有双读不一致为零并持续稳定后，才进入下一步。任何 503 都应定位到迁移映射或订阅回填，不通过配置绕过。

### 3. 客户权益主读

```dotenv
PORTAL_IDENTITY_MODE=dual
PORTAL_ENTITLEMENT_MODE=customer
```

这时未映射旧用户仍可登录，但访问会员内容会失败关闭；因此必须确认所有需要会员能力的账号已经映射。

### 4. 客户身份最终切换

```dotenv
PORTAL_IDENTITY_MODE=customer
PORTAL_ENTITLEMENT_MODE=customer
```

完成后再进入 Contract：把 `customer_id` 改为非空、停止写入旧 `user_id`，并在后续独立版本删除旧列。

## 回滚

任一阶段发生异常，优先回滚配置而不是数据库：

```dotenv
PORTAL_IDENTITY_MODE=legacy
PORTAL_ENTITLEMENT_MODE=legacy
```

Migrate 和双读阶段始终保留 `user_id`，因此旧应用仍可读取原会员归属。不要在业务回滚时删除已经创建的客户、身份或映射；这些数据可能已经产生登录、订单或其他新业务关联。

## 进入 Contract 的门禁

- 所有有效会员订阅 `customer_id IS NOT NULL`；
- legacy/customer 活动订阅集合完全一致；
- 无一对多或多对一映射；
- Portal 生产处于 `customer/customer`；
- 订单与支付已经使用 `customer_id`；
- H5 登录、内容权限、会员中心和个人中心验收通过；
- 数据备份、恢复和应用配置回滚均演练通过。
