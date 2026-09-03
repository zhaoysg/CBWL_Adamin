from __future__ import annotations

import re
import unicodedata

from .enums import IdentityProvider

_E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
_FORBIDDEN_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class InvalidIdentityIdentifier(ValueError):
    """Raised when an identity identifier cannot be canonicalized safely."""


def _nfkc(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise InvalidIdentityIdentifier("identity identifier cannot be empty")
    if _FORBIDDEN_CONTROL_PATTERN.search(normalized):
        raise InvalidIdentityIdentifier("identity identifier contains control characters")
    return normalized


def normalize_identifier(provider: IdentityProvider | str, identifier: str) -> str:
    """Return the canonical value used by the database uniqueness boundary.

    Mobile identities are deliberately strict: callers must first convert a
    local phone number to E.164. The identity layer must not guess a country.
    """

    provider_value = IdentityProvider(provider)
    normalized = _nfkc(identifier)

    if provider_value in {IdentityProvider.PASSWORD, IdentityProvider.EMAIL_OTP}:
        normalized = normalized.casefold()
    elif provider_value is IdentityProvider.MOBILE_OTP:
        compact = re.sub(r"[\s()\-]", "", normalized)
        if not _E164_PATTERN.fullmatch(compact):
            raise InvalidIdentityIdentifier("mobile identity must be an E.164 number")
        normalized = compact

    if len(normalized) > 191:
        raise InvalidIdentityIdentifier("identity identifier exceeds 191 characters")
    return normalized
