import copy
import json
from pathlib import Path

import pytest

from app.core.constants import MessageType
from app.core.exceptions import ValidationFailure
from app.integrations.whatsapp.parser import parse_webhook


def parse(data):
    return parse_webhook(json.dumps(data).encode(), "111", "222")


def test_text_parser(payload):
    event = parse(payload()).messages[0]
    assert event.kind == MessageType.TEXT
    assert "कांद्याची" in event.text
    assert event.display_name == "Test Farmer"


def test_multiple_entries_and_changes(payload):
    data = payload()
    second = copy.deepcopy(data["entry"][0])
    second["changes"].append(copy.deepcopy(second["changes"][0]))
    data["entry"].append(second)
    assert len(parse(data).messages) == 3


@pytest.mark.parametrize("body", [b"{", b"[]", b"null", b'{"object":"wrong","entry":[]}'])
def test_malformed_payload(body):
    with pytest.raises(ValidationFailure):
        parse_webhook(body, "111", "222")


@pytest.mark.parametrize(
    "kind", ["audio", "video", "document", "location", "contacts", "reaction", "future"]
)
def test_unsupported_messages_are_preserved(payload, kind):
    data = payload()
    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    message["type"] = kind
    message[kind] = {"id": "metadata"}
    parsed = parse(data).messages[0]
    assert parsed.raw[kind] == {"id": "metadata"}
    assert parsed.text is None


def test_image_metadata():
    raw = Path("tests/fixtures/whatsapp_image_message.json").read_bytes()
    event = parse_webhook(raw, "111", "222").messages[0]
    assert event.kind == MessageType.IMAGE
    assert event.raw["image"]["id"] == "media-123"


def test_wrong_business_and_phone_are_ignored(payload):
    data = json.dumps(payload()).encode()
    assert not parse_webhook(data, "wrong", "222").messages
    assert not parse_webhook(data, "111", "wrong").messages


def test_malformed_optional_metadata_does_not_crash(payload):
    data = payload()
    data["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = None
    assert parse(data).messages[0].text is None
