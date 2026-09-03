from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin

_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
}


class AuthSubjectModel(ModelMixin):
    """Authentication subject isolated inside one security realm."""

    __tablename__ = "auth_subject"
    __table_args__ = (
        UniqueConstraint("id", "realm", name="uq_auth_subject_id_realm"),
        CheckConstraint(
            "realm IN ('admin', 'customer')",
            name="ck_auth_subject_realm",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_auth_subject_status",
        ),
        CheckConstraint("version_no >= 1", name="ck_auth_subject_version"),
        Index("ix_auth_subject_realm_status", "realm", "status", "id"),
        {"comment": "认证主体", **_TABLE_OPTIONS},
    )

    realm: Mapped[str] = mapped_column(String(32), nullable=False, comment="安全域")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="主体状态",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    identities: Mapped[list[AuthIdentityModel]] = relationship(
        "AuthIdentityModel",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class AuthIdentityModel(ModelMixin):
    """Provider-specific credential or external identity."""

    __tablename__ = "auth_identity"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_auth_identity_subject_realm",
        ),
        UniqueConstraint(
            "realm",
            "provider",
            "identifier_normalized",
            name="uq_auth_identity_realm_provider_identifier",
        ),
        CheckConstraint(
            "realm IN ('admin', 'customer')",
            name="ck_auth_identity_realm",
        ),
        CheckConstraint(
            "provider IN "
            "('password', 'mobile_otp', 'email_otp', 'wechat', 'external')",
            name="ck_auth_identity_provider",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_auth_identity_status",
        ),
        CheckConstraint(
            "(provider = 'password' AND credential_hash IS NOT NULL) OR "
            "(provider <> 'password' AND credential_hash IS NULL)",
            name="ck_auth_identity_credential_shape",
        ),
        CheckConstraint("version_no >= 1", name="ck_auth_identity_version"),
        Index("ix_auth_identity_subject", "subject_id", "realm", "status", "id"),
        {"comment": "认证凭据与外部身份", **_TABLE_OPTIONS},
    )

    subject_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="认证主体ID",
    )
    realm: Mapped[str] = mapped_column(String(32), nullable=False, comment="安全域")
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="认证提供方",
    )
    identifier_normalized: Mapped[str] = mapped_column(
        String(191),
        nullable=False,
        comment="规范化登录标识",
    )
    credential_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="密码凭据哈希，仅password使用",
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="身份验证时间",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="身份状态",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    subject: Mapped[AuthSubjectModel] = relationship(
        "AuthSubjectModel",
        back_populates="identities",
        lazy="raise",
    )


class AdminAccountModel(ModelMixin):
    """Internal administrator actor bridged to the existing RBAC user."""

    __tablename__ = "sys_admin_account"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_sys_admin_account_subject_realm",
        ),
        UniqueConstraint("subject_id", name="uq_sys_admin_account_subject"),
        UniqueConstraint(
            "legacy_sys_user_id",
            name="uq_sys_admin_account_legacy_user",
        ),
        CheckConstraint("realm = 'admin'", name="ck_sys_admin_account_realm"),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_sys_admin_account_status",
        ),
        CheckConstraint("version_no >= 1", name="ck_sys_admin_account_version"),
        Index("ix_sys_admin_account_status", "status", "id"),
        {"comment": "内部管理员业务主体", **_TABLE_OPTIONS},
    )

    subject_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="认证主体ID",
    )
    realm: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="admin",
        comment="固定为admin",
    )
    legacy_sys_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="现有后台RBAC用户ID",
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="管理员显示名称",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="管理员状态",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    subject: Mapped[AuthSubjectModel] = relationship(
        "AuthSubjectModel",
        lazy="raise",
    )


class CustomerModel(ModelMixin):
    """External H5 customer actor; credentials live in auth_identity."""

    __tablename__ = "cw_customer"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_cw_customer_subject_realm",
        ),
        UniqueConstraint("subject_id", name="uq_cw_customer_subject"),
        UniqueConstraint("customer_no", name="uq_cw_customer_no"),
        CheckConstraint("realm = 'customer'", name="ck_cw_customer_realm"),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_cw_customer_status",
        ),
        CheckConstraint(
            "register_source IN ('h5', 'admin_import', 'migration', 'promotion')",
            name="ck_cw_customer_register_source",
        ),
        CheckConstraint("version_no >= 1", name="ck_cw_customer_version"),
        Index("ix_cw_customer_status_created", "status", "created_time", "id"),
        {"comment": "H5外部客户", **_TABLE_OPTIONS},
    )

    subject_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="认证主体ID",
    )
    realm: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="customer",
        comment="固定为customer",
    )
    customer_no: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="不可变客户编号",
    )
    nickname: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="客户昵称",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="头像地址",
    )
    register_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="h5",
        comment="注册来源",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="客户状态",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    subject: Mapped[AuthSubjectModel] = relationship(
        "AuthSubjectModel",
        lazy="raise",
    )
