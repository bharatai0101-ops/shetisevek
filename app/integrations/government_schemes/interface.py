from typing import Protocol


class GovernmentSchemeProvider(Protocol):
    """Extension contract only. No provider is connected by default."""

    async def search(self, state: str, query: str) -> str:
        """Return sourced findings or raise an explicit provider error."""
        ...
