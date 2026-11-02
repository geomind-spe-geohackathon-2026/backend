"""Drop plant_versions.plant_type: gemini's plant document has no class path.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("plant_versions", "plant_type")


def downgrade() -> None:
    op.add_column(
        "plant_versions",
        sa.Column("plant_type", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("plant_versions", "plant_type", server_default=None)
