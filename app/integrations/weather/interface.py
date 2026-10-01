from typing import Protocol


class WeatherProvider(Protocol):
    """Extension contract only. No provider is connected by default."""

    async def forecast(self, latitude: float, longitude: float) -> str:
        """Return sourced findings or raise an explicit provider error."""
        ...
