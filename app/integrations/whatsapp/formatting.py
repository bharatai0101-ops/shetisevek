"""Remove asterisks from outgoing WhatsApp text."""

import re


def format_whatsapp_text(text: str) -> str:
    text = re.sub(r"(?m)^([ \t]*)\*+[ \t]+(?=\S)", r"\1- ", text)
    text = re.sub(r"(?m)^[ \t]*\*+[ \t]*$", "", text)
    text = re.sub(r"(?<=\d)([ \t]*)\*([ \t]*)(?=\d)", r"\1×\2", text)
    return text.replace("*", "")
