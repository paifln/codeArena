"""Create a local signing key without printing or replacing an existing key."""
from pathlib import Path
import re
import secrets

root = Path(__file__).resolve().parents[1]
path = root / ".env"
value = path.read_text(encoding="utf-8-sig") if path.exists() else (root / ".env.example").read_text(encoding="utf-8-sig")
match = re.search(r"^SECRET_KEY=(.*)$", value, re.MULTILINE)
if match is None:
    value += "\nSECRET_KEY=" + secrets.token_hex(64) + "\n"
elif not match.group(1).strip():
    value = value[:match.start()] + "SECRET_KEY=" + secrets.token_hex(64) + value[match.end():]
else:
    print("Existing SECRET_KEY preserved.")
    raise SystemExit(0)
path.write_text(value, encoding="utf-8")
path.chmod(0o600)
print("Local .env initialized. Signing key was not printed.")
