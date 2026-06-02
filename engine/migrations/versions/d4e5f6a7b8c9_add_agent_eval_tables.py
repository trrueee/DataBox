"""add_agent_eval_tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_golden_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("datasource_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("workspace_context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("expected_intent", sa.String(), nullable=True),
        sa.Column("expected_tools_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("forbidden_tools_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("expected_artifact_types_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("expected_final_contains_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("expected_approval_state", sa.String(), nullable=True),
        sa.Column("expected_sql_required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(), nullable=False, server_default="internal"),
        sa.Column("source_case_id", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["datasource_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_golden_tasks_datasource", "agent_golden_tasks", ["datasource_id"])
    op.create_index("ix_agent_golden_tasks_project", "agent_golden_tasks", ["project_id"])
    op.create_index("ix_agent_golden_tasks_intent", "agent_golden_tasks", ["expected_intent"])
    op.create_index("ix_agent_golden_tasks_source", "agent_golden_tasks", ["source"])
    op.create_index("ix_agent_golden_tasks_source_case", "agent_golden_tasks", ["source_case_id"])

    op.create_table(
        "agent_eval_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("datasource_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("source_filter_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_cases", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["datasource_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_eval_runs_datasource", "agent_eval_runs", ["datasource_id"])
    op.create_index("ix_agent_eval_runs_project", "agent_eval_runs", ["project_id"])
    op.create_index("ix_agent_eval_runs_status", "agent_eval_runs", ["status"])

    op.create_table(
        "agent_eval_case_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("eval_run_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("actual_intent", sa.String(), nullable=True),
        sa.Column("actual_tools_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("actual_artifact_types_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("actual_approval_state", sa.String(), nullable=True),
        sa.Column("actual_sql_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("failure_reasons_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("response_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["eval_run_id"], ["agent_eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_golden_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_eval_case_results_run", "agent_eval_case_results", ["eval_run_id"])
    op.create_index("ix_agent_eval_case_results_task", "agent_eval_case_results", ["task_id"])
    op.create_index("ix_agent_eval_case_results_status", "agent_eval_case_results", ["status"])


def downgrade() -> None:
    op.drop_table("agent_eval_case_results")
    op.drop_table("agent_eval_runs")
    op.drop_table("agent_golden_tasks")
