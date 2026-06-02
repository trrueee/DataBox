"""add_agent_approval_and_checkpoint_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_step_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("waiting_approval_id", sa.String(), nullable=True))

    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("risk_level", sa.String(), nullable=False, server_default="warning"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_decision_json", sa.Text(), nullable=False),
        sa.Column("requested_action_json", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_approvals_run", "agent_approvals", ["run_id"])
    op.create_index("ix_agent_approvals_session", "agent_approvals", ["session_id"])
    op.create_index("ix_agent_approvals_status", "agent_approvals", ["status"])

    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("checkpoint_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_step_name", sa.String(), nullable=True),
        sa.Column("next_step_name", sa.String(), nullable=True),
        sa.Column("plan_json", sa.Text(), nullable=True),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("completed_steps_json", sa.Text(), nullable=False),
        sa.Column("pending_steps_json", sa.Text(), nullable=False),
        sa.Column("artifacts_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_checkpoints_run", "agent_checkpoints", ["run_id"])
    op.create_index("ix_agent_checkpoints_session", "agent_checkpoints", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_checkpoints_session", table_name="agent_checkpoints")
    op.drop_index("ix_agent_checkpoints_run", table_name="agent_checkpoints")
    op.drop_table("agent_checkpoints")

    op.drop_index("ix_agent_approvals_status", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_session", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_run", table_name="agent_approvals")
    op.drop_table("agent_approvals")

    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.drop_column("waiting_approval_id")
        batch_op.drop_column("current_step_name")
