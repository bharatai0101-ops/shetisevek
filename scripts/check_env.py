"""Validate configuration without displaying credentials."""

from pydantic import ValidationError

from app.core.config import Settings


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in exc.errors()})
        raise SystemExit("Invalid or missing settings: " + ", ".join(fields)) from None
    print(f"Configuration valid: {settings.app_name} ({settings.app_env})")


if __name__ == "__main__":
    main()
