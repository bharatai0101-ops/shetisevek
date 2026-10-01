from typing import Protocol


class ImageDiagnosisProvider(Protocol):
    """Extension contract only. No provider is connected by default."""

    async def analyze(self, image: bytes, mime_type: str, crop_context: str) -> str:
        """Return sourced findings or raise an explicit provider error."""
        ...
