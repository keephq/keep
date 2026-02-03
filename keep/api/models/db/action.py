from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, UniqueConstraint, CheckConstraint, event
from sqlalchemy.engine import Engine
from sqlmodel import Field, SQLModel, TEXT


# ----------------------------
# Helpers
# ----------------------------

def utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


# If you use SQLite, enforce FK constraints (SQLite defaults to OFF, because fun).
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # Non-sqlite DBs will land here. No need to be dramatic.
        pass


# ----------------------------
# Base Mixins
# ----------------------------

class UUIDPrimaryKeyMixin(SQLModel):
    id: str = Field(default_factory=uuid_str, primary_key=True, index=True)


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)


class SoftDeleteMixin(SQLModel):
    is_deleted: bool = Field(default=False, nullable=False, index=True)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True, index=True)


# ----------------------------
# Action Model
# ----------------------------

class Action(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    """
    Action definition with sane constraints, indexes, and audit-friendly timestamps.
    """

    __tablename__ = "action"

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "use", name="uq_action_tenant_name_use"),
        # Avoid empty strings in critical identity fields.
        CheckConstraint("length(trim(tenant_id)) > 0", name="ck_action_tenant_id_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="ck_action_name_nonempty"),
        CheckConstraint("length(trim(use)) > 0", name="ck_action_use_nonempty"),
        CheckConstraint("length(trim(installed_by)) > 0", name="ck_action_installed_by_nonempty"),
    )

    # FK + index because you'll filter by tenant constantly
    tenant_id: str = Field(
        foreign_key="tenant.id",
        nullable=False,
        index=True,
        max_length=64,   # keep index-friendly; adjust if your tenant IDs are longer
    )

    # "use" is usually a category/purpose. Small and indexed.
    use: str = Field(nullable=False, index=True, max_length=32)

    # name usually participates in uniqueness and search
    name: str = Field(nullable=False, index=True, max_length=128)

    description: Optional[str] = Field(default=None, max_length=512)

    # TEXT for raw payload, but force non-null at DB level
    action_raw: str = Field(sa_column=Column(TEXT, nullable=False))

    installed_by: str = Field(nullable=False, index=True, max_length=96)

    # Keep the original field too if you want it explicitly.
    # You can remove this if created_at is enough.
    installation_time: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    # ----------------------------
    # Pydantic / SQLModel validation hooks
    # ----------------------------
    def _clean(self) -> None:
        # Normalize whitespace to prevent "same but different" uniqueness bugs.
        self.tenant_id = self.tenant_id.strip()
        self.use = self.use.strip()
        self.name = self.name.strip()
        self.installed_by = self.installed_by.strip()
        if self.description is not None:
            self.description = self.description.strip()

        # Hard rejects (fail fast)
        if not self.tenant_id:
            raise ValueError("tenant_id cannot be empty.")
        if not self.use:
            raise ValueError("use cannot be empty.")
        if not self.name:
            raise ValueError("name cannot be empty.")
        if not self.installed_by:
            raise ValueError("installed_by cannot be empty.")

    def touch_update(self) -> None:
        """Call this before saving updates."""
        self.updated_at = utcnow()

    def soft_delete(self) -> None:
        """Soft delete without losing audit history."""
        self.is_deleted = True
        self.deleted_at = utcnow()
        self.touch_update()

    class Config:
        orm_mode = True