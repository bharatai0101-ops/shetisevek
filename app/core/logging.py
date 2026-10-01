import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
SAFE_FIELDS = {"request_id", "event_id", "job_id", "user_id", "message_id", "error_code", "state"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Fixed application events only; provider/exception bodies are never serialized.
        data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.msg if record.name.startswith("app.") else "library_event",
            "logger": record.name,
            "request_id": request_id_context.get(),
        }
        for field in SAFE_FIELDS:
            if hasattr(record, field):
                data[field] = str(getattr(record, field))
        return json.dumps(data, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    for name in ("httpx", "httpcore", "google_genai", "sqlalchemy.engine", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)
