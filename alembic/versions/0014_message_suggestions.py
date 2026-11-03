"""Keep the next steps geomind suggested with an assistant message.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages", sa.Column("suggestions", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("messages", "suggestions")
