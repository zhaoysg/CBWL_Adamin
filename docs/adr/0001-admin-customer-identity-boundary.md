# ADR-0001：内部管理员与外部客户身份边界

- 状态：Accepted for implementation
- 日期：2026-09-02
- 范围：CBWL Platform / Admin API / Portal API / H5

## 背景

`sys_user` 当前同时承担后台 RBAC 用户和 H5 用户的角色。会员订阅与订单也以
`sys_user.id` 作为用户外键。这个模型适合脚手架早期验证，但不适合作为长期生产
边界：内部员工和外部客户拥有不同的凭据、生命周期、审计、风控和授权模型。

## 决策

采用“身份凭据 Identity + 业务主体 Actor”结构：

```text
auth_subject
  ├── auth_identity
  ├── sys_admin_account -> legacy sys_user / RBAC
  └── cw_customer
```

- `admin` 与 `customer` 是不同 realm。
- 登录标识唯一性按 `(realm, provider, identifier_normalized)` 控制。
- H5 客户凭据不进入 `cw_customer`；管理员凭据不进入订单或会员表。
- `sys_admin_account` 在过渡期一对一桥接现有 `sys_user`，保留后台 RBAC。
- `cw_customer` 是所有外部客户业务的最终归属主体。
- Admin Token 与 Portal Token 使用不同 audience、Cookie、Redis namespace。
- 一套后端代码库提供 Admin API 与 Portal API 两个应用入口，共享领域服务与 MySQL。

## 为什么不建立两个业务数据库

商品、价格、会员、订单和支付属于同一业务事务域。按“管理页面/用户页面”拆数据库会
引入同步、重复事件、跨库事务和回滚问题。当前按环境使用一套 MySQL 业务数据库，
通过不同 API、数据库账号最小权限和应用层对象授权隔离。

## 分阶段迁移

1. M1：新增四张身份表，不修改现有业务外键。
2. 回填管理员桥接关系和外部客户映射，输出不可变映射报告。
3. M2：会员订阅、订单及后续客户业务改为 `customer_id`。
4. 双读校验通过后停止读取客户侧 `sys_user.id`。
5. 删除兼容代码前完成生产备份、回滚演练与审计核对。

## 事务边界

创建客户时，subject、identity、customer 必须在同一个数据库事务中写入。
Domain service 只 `flush`，不自行 `commit`；请求级应用服务拥有最终提交与回滚。
唯一约束是并发注册的最终裁决，预查询不能替代数据库约束。

## 后果

正面：身份边界稳定、管理员与客户不再混淆、可扩展手机号/微信/SSO/MFA，并为两个
API 应用入口奠定基础。

成本：需要一次客户数据回填和会员/订单外键迁移；PR #5 必须在身份迁移之后重放。
