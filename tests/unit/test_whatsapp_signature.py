import hashlib
import hmac

from app.integrations.whatsapp.signature import valid_signature


def test_valid_signature_and_exact_bytes():
    body = b'{"a": 1}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert valid_signature(body, signature, "secret")
    assert not valid_signature(b'{"a":1}', signature, "secret")
    assert not valid_signature(body, signature, "wrong")


def test_invalid_signature():
    for signature in ("", "sha256=bad", "non-ascii-\u2603"):
        assert not valid_signature(b"{}", signature, "secret")
