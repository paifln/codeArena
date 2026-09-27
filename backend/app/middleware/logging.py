"""Allowlisted JSON events: never serialize request bodies or exceptions."""
import json
import logging
import time


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"time": time.time(), "level": record.levelname,
                   "logger": record.name}
        # Application messages are fixed templates; exclude exception text/tracebacks.
        payload["event"] = record.getMessage() if record.name.startswith("codearena") else "service.log"
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=True)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


def event(name, **fields):
    logging.getLogger("codearena.events").info(name, extra={"fields": fields})
