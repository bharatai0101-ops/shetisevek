from typing import Protocol


class MarketPriceProvider(Protocol):
    """Extension contract only. No provider is connected by default."""

    async def prices(self, crop: str, market: str) -> str:
        """Return sourced findings or raise an explicit provider error."""
        ...
