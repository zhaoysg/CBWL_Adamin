from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CLOSED = "closed"
    REFUNDING = "refunding"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    FAILED = "failed"


class BillingProvider(StrEnum):
    SANDBOX = "sandbox"
    MANUAL = "manual"


class PaymentAttemptStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentEventProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    REJECTED = "rejected"
    FAILED = "failed"


class RefundStatus(StrEnum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutboxEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


def sql_enum_values(enum_type: type[StrEnum]) -> str:
    """Return trusted enum values as a SQL CHECK literal list."""

    return ", ".join(f"'{member.value}'" for member in enum_type)
