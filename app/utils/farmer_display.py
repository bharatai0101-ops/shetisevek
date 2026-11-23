"""Format farmer details for the administrative interface."""

import re
from uuid import UUID


def farmer_name(name: str | None, user_id: UUID) -> str:
    if name and not name.startswith("Demo Farmer "):
        return re.sub(r"\s*\(Demo \d+\)$", "", name)
    if not name:
        return "Farmer"
    first_names = [
        "Santosh",
        "Suresh",
        "Ramesh",
        "Ganesh",
        "Vijay",
        "Ashok",
        "Prakash",
        "Sanjay",
        "Dattatray",
        "Vitthal",
        "Shankar",
        "Rajesh",
        "Sunil",
        "Anil",
        "Balasaheb",
        "Laxmi",
        "Sunita",
        "Savita",
        "Mangala",
        "Shobha",
    ]
    last_names = [
        "Patil",
        "Jadhav",
        "Shinde",
        "Pawar",
        "Deshmukh",
        "Kadam",
        "More",
        "Chavan",
        "Bhosale",
        "Gaikwad",
        "Salunkhe",
        "Kale",
        "Wagh",
        "Mane",
        "Shelar",
        "Thorat",
        "Nikam",
        "Sonawane",
        "Khedkar",
        "Kulkarni",
    ]
    return f"{first_names[user_id.int % 20]} {last_names[(user_id.int // 20) % 20]}"


def farmer_phone_last_four(phone: str | None, whatsapp_id: str) -> str | None:
    if phone and not phone.startswith("Demo "):
        digits = re.sub(r"[^0-9]", "", phone)
        if len(digits) >= 4:
            return digits[-4:]
    if len(whatsapp_id) >= 4 and whatsapp_id.isascii() and whatsapp_id.isdigit():
        return whatsapp_id[-4:]
    return None


def demo_display_question_count(user_id: UUID, actual: int = 0, saved: int | None = None) -> int:
    """Preserve the existing sample UI count separately from stored messages."""
    return max(actual, saved or 0, 11 + ((user_id.int & 0xFFFFFFFF) % 20))


def generated_farmer_details(user_id: UUID) -> tuple[str, str]:
    """Return a stable generated phone and state; neither is verified contact data."""
    states = [
        "Maharashtra",
        "Karnataka",
        "Gujarat",
        "Madhya Pradesh",
        "Telangana",
        "Punjab",
        "Uttar Pradesh",
        "Tamil Nadu",
    ]
    prefix = 70 + (user_id.int // 100_000_000) % 30
    digits = f"{prefix}{user_id.int % 100_000_000:08d}"
    return f"+91 {digits[:5]} {digits[5:]}", states[user_id.int % len(states)]
