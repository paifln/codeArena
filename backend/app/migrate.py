"""Run from backend: python -m app.migrate. Never runs in the judge worker."""

from pathlib import Path
from alembic.config import Config
from alembic import command


def upgrade():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade()
