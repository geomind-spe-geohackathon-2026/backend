"""Store the count of missing values on each case version.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "case_versions",
        sa.Column("missing", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("case_versions", "missing", server_default=None)


def downgrade() -> None:
    op.drop_column("case_versions", "missing")
