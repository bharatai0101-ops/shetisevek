class AppError(Exception):
    code = "application_error"
    status_code = 500


class ValidationFailure(AppError):
    code = "invalid_payload"
    status_code = 400


class WebhookAuthenticationError(AppError):
    code = "webhook_authentication_failed"
    status_code = 401


class DatabaseUnavailable(AppError):
    code = "database_unavailable"
    status_code = 503


class LostJobClaim(AppError):
    code = "job_claim_lost"


class ExternalError(AppError):
    def __init__(self, code: str, retryable: bool = False, uncertain: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain


class RetryableExternalError(ExternalError):
    def __init__(self, code: str) -> None:
        super().__init__(code, retryable=True)


class PermanentExternalError(ExternalError):
    pass
