from slowapi import Limiter
from slowapi.util import get_remote_address

# Single API process, as required by the SQLite deployment architecture.
limiter = Limiter(key_func=get_remote_address, application_limits=["100/minute"])
