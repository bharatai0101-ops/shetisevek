def whatsapp_text(value: str, limit: int = 4000) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
