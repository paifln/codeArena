"""Contest displays, timeline, physical rewards and durable bulk rejudge."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    for column in (
        sa.Column("penalty_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column(
            "languages",
            sa.JSON(),
            nullable=False,
            server_default='["python3","cpp20","java17"]',
        ),
        sa.Column(
            "public_scoreboard", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("logo_data", sa.Text(), nullable=False, server_default=""),
        sa.Column("revealed_ids", sa.JSON(), nullable=False, server_default="[]"),
    ):
        op.add_column("contests", column)
    op.add_column(
        "teams",
        sa.Column("organization", sa.String(120), nullable=False, server_default=""),
    )
    op.add_column(
        "teams", sa.Column("created_at", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "clarifications",
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
    )
    op.execute("UPDATE clarifications SET status='ANSWERED' WHERE answer != ''")
    op.execute(
        "ALTER TABLE audit_logs ADD COLUMN contest_id INTEGER REFERENCES contests(id)"
    )
    op.create_index("ix_audit_logs_contest_id", "audit_logs", ["contest_id"])
    op.create_table(
        "contest_presence",
        sa.Column(
            "contest_id",
            sa.Integer(),
            sa.ForeignKey("contests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("last_seen", sa.Float(), nullable=False),
        sa.Column("connected", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "puzzle_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contest_id", sa.Integer(), sa.ForeignKey("contests.id"), nullable=False
        ),
        sa.Column("identity", sa.String(40), nullable=False),
        sa.Column(
            "problem_id", sa.Integer(), sa.ForeignKey("problems.id"), nullable=False
        ),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id"),
            nullable=False,
        ),
        sa.Column("solved_at", sa.Float(), nullable=False),
        sa.Column("delivered_at", sa.Float()),
        sa.Column("delivered_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("contest_id", "identity", "problem_id"),
    )
    op.create_index("ix_puzzle_rewards_contest_id", "puzzle_rewards", ["contest_id"])
    op.create_table(
        "rejudge_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contest_id", sa.Integer(), sa.ForeignKey("contests.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("remaining_ids", sa.JSON(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("finished_at", sa.Float()),
    )


def downgrade():
    for table in ("rejudge_batches", "puzzle_rewards", "contest_presence"):
        op.drop_table(table)
    op.drop_index("ix_audit_logs_contest_id", table_name="audit_logs")
    op.drop_column("audit_logs", "contest_id")
    op.drop_column("clarifications", "status")
    for name in ("organization", "created_at"):
        op.drop_column("teams", name)
    for name in (
        "penalty_minutes",
        "languages",
        "public_scoreboard",
        "logo_data",
        "revealed_ids",
    ):
        op.drop_column("contests", name)
