from enum import Enum


class ConversationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    LOCATION = "LOCATION"
    CONTACT = "CONTACT"
    INTERACTIVE = "INTERACTIVE"
    BUTTON = "BUTTON"
    REACTION = "REACTION"
    UNKNOWN = "UNKNOWN"


class MessageStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    GENERATED = "GENERATED"
    PENDING_SEND = "PENDING_SEND"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class ProcessingJobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class FarmerCropStatus(str, Enum):
    ACTIVE = "ACTIVE"
    HARVESTED = "HARVESTED"
    INACTIVE = "INACTIVE"


DELIVERY_UNCERTAIN = "delivery_uncertain"
