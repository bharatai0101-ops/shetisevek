import hashlib
import json
from typing import Any
from uuid import UUID


def event_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def advisory_key(identifier: UUID) -> int:
    return int.from_bytes(hashlib.sha256(identifier.bytes).digest()[:8], "big", signed=True)
