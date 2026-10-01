import hashlib
import hmac

from app.core.security import secure_compare


def valid_signature(raw_body: bytes, signature: str, app_secret: str) -> bool:
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return secure_compare(expected, signature)
