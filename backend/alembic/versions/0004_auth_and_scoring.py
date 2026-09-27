"""Refresh revocation and independent educational scoring."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("refresh_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False))
    op.execute("UPDATE contests SET scoring='EDUCATIONAL' WHERE mode='EDUCATIONAL' AND scoring='ICPC'")
    op.execute("UPDATE contests SET mode='INDIVIDUAL' WHERE mode='EDUCATIONAL'")
    # Old opaque cookies cannot be interpreted as JWTs. Passwords remain intact.
    op.execute("DELETE FROM sessions")


def downgrade():
    op.execute("UPDATE contests SET mode='EDUCATIONAL', scoring='ICPC' WHERE scoring='EDUCATIONAL' AND mode='INDIVIDUAL'")
    op.execute("UPDATE contests SET scoring='ICPC' WHERE scoring='EDUCATIONAL'")
    op.drop_table("refresh_tokens")
