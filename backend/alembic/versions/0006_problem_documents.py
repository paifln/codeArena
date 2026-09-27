"""Bounded problem documents, stored with the database and its backups."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "problem_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "problem_id",
            sa.Integer(),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_problem_documents_problem_id", "problem_documents", ["problem_id"]
    )


def downgrade():
    op.drop_table("problem_documents")
