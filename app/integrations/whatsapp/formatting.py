"""Normalize generated Markdown to WhatsApp's single-asterisk bold syntax."""

import re


def format_whatsapp_text(text: str) -> str:
    # Keep code examples literal; format only the surrounding prose.
    parts = re.split(r"(```[\s\S]*?```|`[^`\n]*`)", text)
    for index in range(0, len(parts), 2):
        prose = re.sub(r"(?m)^([ \t]*)\*[ \t]+(?=\S)", r"\1- ", parts[index])
        prose = re.sub(r"(?<!\*)\*\*([^\n*]+)\*\*(?!\*)", r"*\1*", prose)
        prose = re.sub(r"(?m)^[ \t]*\*{1,2}[ \t]*$", "", prose)
        parts[index] = prose
    return "".join(parts)
