"""Add the shared knowledge, connectors, and a project's memory and connector choices.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("section", sa.String(16), nullable=False),
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_by_kind", sa.String(16), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "section", "project_id", "entry_id", name="uq_knowledge_entries_entry"
        ),
    )
    op.create_index(
        "ix_knowledge_entries_section_created_id",
        "knowledge_entries",
        ["section", "created", "id"],
    )
    op.create_table(
        "connectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("transport", sa.String(8), nullable=False),
        sa.Column("auth", sa.String(8), nullable=False),
        sa.Column("header_name", sa.String(255), nullable=True),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tools", postgresql.JSONB(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("projects", sa.Column("memory", sa.String(3), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "connectors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "connectors")
    op.drop_column("projects", "memory")
    op.drop_table("connectors")
    op.drop_index("ix_knowledge_entries_section_created_id", "knowledge_entries")
    op.drop_table("knowledge_entries")
