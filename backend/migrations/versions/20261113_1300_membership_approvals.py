"""membership approvals and business join codes

Revision ID: b7e1c0a4f2d1
Revises: 9d5ac2402023
Created: 2026-11-13 13:00:00

Existing memberships are back-filled as ``approved`` so nobody who could use
the app before this migration is locked out by it.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7e1c0a4f2d1"
down_revision = "9d5ac2402023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("memberships") as b:
        b.add_column(sa.Column("status", sa.String(length=12), nullable=False,
                               server_default="approved"))
        b.add_column(sa.Column("approvals_json", sa.JSON(), nullable=False,
                               server_default="[]"))
        b.create_index("ix_memberships_status", ["status"])
    with op.batch_alter_table("businesses") as b:
        b.add_column(sa.Column("join_code", sa.String(length=16), nullable=True))
        b.create_unique_constraint("uq_businesses_join_code", ["join_code"])


def downgrade() -> None:
    with op.batch_alter_table("businesses") as b:
        b.drop_constraint("uq_businesses_join_code", type_="unique")
        b.drop_column("join_code")
    with op.batch_alter_table("memberships") as b:
        b.drop_index("ix_memberships_status")
        b.drop_column("approvals_json")
        b.drop_column("status")
