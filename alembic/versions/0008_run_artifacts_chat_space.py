"""Let a chat artifact have no run.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("run_artifacts", "run_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM run_artifacts WHERE run_id IS NULL")
    op.alter_column("run_artifacts", "run_id", existing_type=sa.Uuid(), nullable=False)
