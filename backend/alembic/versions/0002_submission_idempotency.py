"""Deduplicate retried submission requests without changing existing records."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("submissions", sa.Column("request_id", sa.String(36), nullable=True))
    op.create_index(
        "ix_submission_user_request",
        "submissions",
        ["user_id", "request_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_submission_user_request", table_name="submissions")
    op.drop_column("submissions", "request_id")
