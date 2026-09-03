from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.base_schema import AuthSchema

PortalActorType = Literal["anonymous", "legacy", "customer"]


@dataclass(frozen=True, slots=True)
class PortalPrincipal:
    actor_type: PortalActorType
    auth: AuthSchema | None
    legacy_user_id: int | None = None
    customer_id: int | None = None
    subject_id: int | None = None

    def __post_init__(self) -> None:
        if self.actor_type == "anonymous":
            if any(
                value is not None
                for value in (
                    self.auth,
                    self.legacy_user_id,
                    self.customer_id,
                    self.subject_id,
                )
            ):
                raise ValueError("anonymous principal cannot contain identity data")
            return

        if self.auth is None or self.legacy_user_id is None:
            raise ValueError("authenticated principal requires legacy compatibility data")
        if self.legacy_user_id <= 0:
            raise ValueError("legacy_user_id must be positive")
        if self.auth.user.id != self.legacy_user_id:
            raise ValueError("auth user and legacy_user_id must match")

        if self.actor_type == "customer":
            if self.customer_id is None or self.subject_id is None:
                raise ValueError("customer principal requires customer and subject IDs")
            if self.customer_id <= 0 or self.subject_id <= 0:
                raise ValueError("customer and subject IDs must be positive")
        elif self.customer_id is not None or self.subject_id is not None:
            raise ValueError("legacy principal cannot contain customer identity data")

    @property
    def is_authenticated(self) -> bool:
        return self.actor_type != "anonymous"

    @classmethod
    def anonymous(cls) -> PortalPrincipal:
        return cls(actor_type="anonymous", auth=None)


__all__ = ["PortalActorType", "PortalPrincipal"]
