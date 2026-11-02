"""Add the budget caps of a project.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("budget_max_tokens", sa.BigInteger(), nullable=True)
    )
    op.add_column("projects", sa.Column("budget_max_cost", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "budget_max_cost")
    op.drop_column("projects", "budget_max_tokens")
