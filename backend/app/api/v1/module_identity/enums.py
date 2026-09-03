from enum import StrEnum


class IdentityRealm(StrEnum):
    ADMIN = "admin"
    CUSTOMER = "customer"


class IdentityProvider(StrEnum):
    PASSWORD = "password"  # nosec B105 - provider name, not a credential
    MOBILE_OTP = "mobile_otp"
    EMAIL_OTP = "email_otp"
    WECHAT = "wechat"
    EXTERNAL = "external"


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class CustomerRegisterSource(StrEnum):
    H5 = "h5"
    ADMIN_IMPORT = "admin_import"
    MIGRATION = "migration"
    PROMOTION = "promotion"
