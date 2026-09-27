"""Explicit completion for individuals and teams."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "participation_completions",
        sa.Column(
            "contest_id", sa.Integer(), sa.ForeignKey("contests.id"), primary_key=True
        ),
        sa.Column("identity", sa.String(40), primary_key=True),
        sa.Column("completed_at", sa.Float(), nullable=False),
        sa.Column(
            "completed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
    )


def downgrade():
    op.drop_table("participation_completions")
