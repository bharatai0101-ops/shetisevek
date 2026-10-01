from app.core.exceptions import ExternalError


class GeminiError(ExternalError):
    """Safe generation error with explicit retry classification."""
