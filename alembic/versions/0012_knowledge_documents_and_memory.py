"""Shared Knowledge documents, and the agents' memory under its own name.

A document may belong to no project: the shared Knowledge every project searches. The
memory table of 0011 holds only the agents' own memory, so it is named for it.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("documents", "project_id", existing_type=sa.Uuid(), nullable=True)
    op.rename_table("knowledge_entries", "memory_entries")
    op.execute(
        "ALTER TABLE memory_entries RENAME CONSTRAINT uq_knowledge_entries_entry "
        "TO uq_memory_entries_entry"
    )
    op.execute(
        "ALTER INDEX ix_knowledge_entries_section_created_id "
        "RENAME TO ix_memory_entries_section_created_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_memory_entries_section_created_id "
        "RENAME TO ix_knowledge_entries_section_created_id"
    )
    op.execute(
        "ALTER TABLE memory_entries RENAME CONSTRAINT uq_memory_entries_entry "
        "TO uq_knowledge_entries_entry"
    )
    op.rename_table("memory_entries", "knowledge_entries")
    op.execute("DELETE FROM documents WHERE project_id IS NULL")
    op.alter_column("documents", "project_id", existing_type=sa.Uuid(), nullable=False)
