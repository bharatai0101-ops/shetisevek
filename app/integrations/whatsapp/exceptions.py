from app.core.exceptions import ExternalError


class MetaAPIError(ExternalError):
    """Contains only sanitized codes, never raw provider error messages."""
