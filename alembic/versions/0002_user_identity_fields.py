"""Add user name and role and rename is_active to active.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "is_active", new_column_name="active")
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=16),
            server_default="member",
            nullable=False,
        ),
    )
    op.execute("UPDATE users SET name = split_part(email, '@', 1)")
    op.alter_column("users", "name", nullable=False)
    op.alter_column("users", "role", server_default=None)
    op.alter_column("users", "created_at", server_default=None)


def downgrade() -> None:
    op.alter_column("users", "created_at", server_default=sa.text("now()"))
    op.drop_column("users", "role")
    op.drop_column("users", "name")
    op.alter_column("users", "active", new_column_name="is_active")
