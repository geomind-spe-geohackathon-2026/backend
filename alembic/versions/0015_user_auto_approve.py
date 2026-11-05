"""Keep each user's auto-approve answer for new chats (QA-292).

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auto_approve", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "auto_approve")
