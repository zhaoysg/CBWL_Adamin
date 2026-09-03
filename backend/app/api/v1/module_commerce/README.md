# M4 Commerce Expand

This module introduces reversible customer-owned order and normalized payment facts.

- Order price, currency, plan name/code and duration are copied from the active server-side member plan.
- `legacy_user_id` and `customer_id` coexist during migration; at least one owner is required.
- Idempotency is enforced by database unique constraints, not process-local locks.
- Provider adapters must verify signatures before constructing `VerifiedPaymentEventSchema`.
- Raw callback bodies, signatures, tokens and credentials are never stored in commerce tables.
- The caller owns the outer database transaction. Services only use `flush()` and savepoints.
- A successful payment changes the order/payment aggregate only. Membership grant and outbox delivery belong to the next transactional phase.
