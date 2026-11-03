"""Name the shared and project documents ``rag`` and the connectors ``mcp``.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("documents", "rag_documents")
    op.execute(
        "ALTER INDEX ix_documents_project_id_created_id "
        "RENAME TO ix_rag_documents_project_id_created_id"
    )
    op.rename_table("connectors", "mcp_servers")
    op.alter_column("projects", "connectors", new_column_name="mcp")


def downgrade() -> None:
    op.alter_column("projects", "mcp", new_column_name="connectors")
    op.rename_table("mcp_servers", "connectors")
    op.execute(
        "ALTER INDEX ix_rag_documents_project_id_created_id "
        "RENAME TO ix_documents_project_id_created_id"
    )
    op.rename_table("rag_documents", "documents")
