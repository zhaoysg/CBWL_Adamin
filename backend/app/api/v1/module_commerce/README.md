# M4 Commerce Expand

This module establishes the canonical reversible order and normalized-payment aggregate.

- `cw_order`, `cw_payment_attempt`, and `cw_payment_event` are the only M4 commerce tables.
- Order price, currency, plan name/code, and duration are copied from the active server-side member plan; clients cannot submit trusted monetary values.
- `legacy_user_id` and `customer_id` coexist during migration. Customer sessions must resolve to an active customer/auth subject and a live migrated mapping. A mapped legacy session cannot create new legacy-only orders.
- Database uniqueness, savepoints, and row locks provide idempotency and concurrency control. One order can have at most one `created` or `processing` payment attempt at a time.
- Aggregate writes use a stable order-then-attempt lock order. A normalized payment event and its accepted state transition flush inside one savepoint, so an integrity error does not poison the caller-owned outer transaction.
- Provider adapters must verify signatures before constructing `VerifiedPaymentEventSchema`. Raw callback bodies, signatures, tokens, cookies, and credentials are never stored.
- Payment success is evaluated against the provider event's `occurred_at`, not callback delivery time, so a legitimately late callback can still settle an event that occurred before expiry.
- Commerce tables use `utf8mb4_bin` in MySQL so provider IDs and idempotency keys retain case-sensitive semantics.
- A successful event updates only the order/payment aggregate. Membership grant and outbox delivery remain a later transactional phase.
