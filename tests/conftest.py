"""Isolated test credentials, unrelated to the deployment .env."""
import os
import secrets

os.environ["SECRET_KEY"] = secrets.token_hex(64)
