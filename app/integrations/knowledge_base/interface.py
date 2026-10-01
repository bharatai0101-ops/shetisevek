from typing import Protocol


class KnowledgeBaseProvider(Protocol):
    """Extension contract only. No provider is connected by default."""

    async def search(self, query: str, language: str) -> str:
        """Return sourced findings or raise an explicit provider error."""
        ...
