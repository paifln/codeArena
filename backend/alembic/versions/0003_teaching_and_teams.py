"""Teaching modes, teams, weighted tests and feedback."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("problems", sa.Column("editorial", sa.Text(), nullable=False, server_default=""))
    op.add_column("test_cases", sa.Column("weight", sa.Integer(), nullable=False, server_default="1"))
    for name, default in (("mode", "INDIVIDUAL"), ("scoring", "ICPC")):
        op.add_column("contests", sa.Column(name, sa.String(16), nullable=False, server_default=default))
    op.add_column("contests", sa.Column("practice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("teams", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("contest_id", sa.Integer(), sa.ForeignKey("contests.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("name", sa.String(100), nullable=False), sa.UniqueConstraint("contest_id", "name"))
    op.create_table("team_members",
                    sa.Column("contest_id", sa.Integer(), sa.ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
                    sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False))
    # Native ADD COLUMN avoids rebuilding the parent table and cascading child rows.
    op.execute("ALTER TABLE submissions ADD COLUMN team_id INTEGER REFERENCES teams(id)")
    op.add_column("submissions", sa.Column("is_practice", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("submissions", sa.Column("score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("submissions", sa.Column("feedback", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE submissions SET score=100 WHERE status='ACCEPTED' AND kind='SUBMIT'")


def downgrade():
    for name in ("feedback", "score", "is_practice", "team_id"):
        op.drop_column("submissions", name)
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_column("contests", "practice_enabled")
    op.drop_column("contests", "scoring")
    op.drop_column("contests", "mode")
    op.drop_column("test_cases", "weight")
    op.drop_column("problems", "editorial")
