"""Identity boundary for internal administrators and external customers.

M1 intentionally introduces only additive tables. Existing membership and
billing foreign keys are migrated in M2 after customer backfill has been
verified.
"""

from .model import (
    AdminAccountModel,
    AuthIdentityModel,
    AuthSubjectModel,
    CustomerModel,
)
from .service import IdentityService

__all__ = [
    "AdminAccountModel",
    "AuthIdentityModel",
    "AuthSubjectModel",
    "CustomerModel",
    "IdentityService",
]
