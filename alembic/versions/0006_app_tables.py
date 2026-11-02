"""Add the app tables and drop plant_versions.plant_type.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_name", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("link_route", sa.String(length=64), nullable=True),
        sa.Column("link_id", sa.String(length=64), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_activity_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activity"),
    )
    op.create_index(
        "ix_activity_project_id_created_id",
        "activity",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_table(
        "case_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_case_versions_author_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_case_versions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_versions"),
        sa.UniqueConstraint("project_id", "number", name="uq_case_versions_project_id"),
    )
    op.create_table(
        "chats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_chats_author_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_chats_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chats"),
    )
    op.create_index(
        "ix_chats_project_id_created_id",
        "chats",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("searchable", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_documents_author_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_documents_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index(
        "ix_documents_project_id_created_id",
        "documents",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_table(
        "case_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("case_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_version_id"],
            ["case_versions.id"],
            name="fk_case_files_case_version_id_case_versions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_case_files_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_files"),
        sa.UniqueConstraint(
            "case_version_id", "name", name="uq_case_files_case_version_id"
        ),
    )
    op.create_table(
        "chat_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            name="fk_chat_states_chat_id_chats",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_states"),
        sa.UniqueConstraint("chat_id", "version", name="uq_chat_states_chat_id"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("loop", sa.String(length=64), nullable=True),
        sa.Column("request", postgresql.JSONB(), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Double(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_runs_author_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            name="fk_runs_chat_id_chats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_runs_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
    )
    op.create_index(
        "ix_runs_chat_id_created", "runs", ["chat_id", "created"], unique=False
    )
    op.create_index(
        "ix_runs_project_id_created_id",
        "runs",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_index(
        "ix_runs_project_id_status", "runs", ["project_id", "status"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            name="fk_messages_chat_id_chats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_messages_run_id_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index(
        "ix_messages_chat_id_created_id",
        "messages",
        ["chat_id", "created", "id"],
        unique=False,
    )
    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("data_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("data_json", postgresql.JSONB(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            name="fk_run_artifacts_chat_id_chats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_artifacts_run_id_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_artifacts"),
    )
    op.create_index(
        "ix_run_artifacts_chat_id_key_created",
        "run_artifacts",
        ["chat_id", "key", "created"],
        unique=False,
    )
    op.create_index(
        "ix_run_artifacts_run_id_key", "run_artifacts", ["run_id", "key"], unique=False
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_events_run_id_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_events"),
    )
    op.create_index(
        "ix_run_events_run_id_sequence",
        "run_events",
        ["run_id", "sequence"],
        unique=False,
    )
    op.create_table(
        "studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("started_by_kind", sa.String(length=16), nullable=False),
        sa.Column("started_by_name", sa.String(length=255), nullable=False),
        sa.Column("started_by_run_id", sa.Uuid(), nullable=True),
        sa.Column("case_version", sa.Integer(), nullable=True),
        sa.Column("plant_version", sa.Integer(), nullable=True),
        sa.Column("missing", postgresql.JSONB(), nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_studies_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["started_by_run_id"],
            ["runs.id"],
            name="fk_studies_started_by_run_id_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_studies"),
    )
    op.create_index(
        "ix_studies_project_id_created_id",
        "studies",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_index(
        "ix_studies_project_id_status",
        "studies",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=True),
        sa.Column("plant_version", sa.Integer(), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_results_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.id"],
            name="fk_results_study_id_studies",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_results"),
    )
    op.create_index(
        "ix_results_project_id_created_id",
        "results",
        ["project_id", "created", "id"],
        unique=False,
    )
    op.create_index("ix_results_study_id", "results", ["study_id"], unique=False)
    op.drop_column("plant_versions", "plant_type")


def downgrade() -> None:
    op.add_column(
        "plant_versions",
        sa.Column("plant_type", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("plant_versions", "plant_type", server_default=None)
    op.drop_index("ix_results_study_id", table_name="results")
    op.drop_index("ix_results_project_id_created_id", table_name="results")
    op.drop_table("results")
    op.drop_index("ix_studies_project_id_status", table_name="studies")
    op.drop_index("ix_studies_project_id_created_id", table_name="studies")
    op.drop_table("studies")
    op.drop_index("ix_run_events_run_id_sequence", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_run_artifacts_run_id_key", table_name="run_artifacts")
    op.drop_index("ix_run_artifacts_chat_id_key_created", table_name="run_artifacts")
    op.drop_table("run_artifacts")
    op.drop_index("ix_messages_chat_id_created_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_runs_project_id_status", table_name="runs")
    op.drop_index("ix_runs_project_id_created_id", table_name="runs")
    op.drop_index("ix_runs_chat_id_created", table_name="runs")
    op.drop_table("runs")
    op.drop_table("chat_states")
    op.drop_table("case_files")
    op.drop_index("ix_documents_project_id_created_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_chats_project_id_created_id", table_name="chats")
    op.drop_table("chats")
    op.drop_table("case_versions")
    op.drop_index("ix_activity_project_id_created_id", table_name="activity")
    op.drop_table("activity")
