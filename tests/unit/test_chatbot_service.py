from unittest.mock import AsyncMock

from app.schemas.farmer import FarmerContext, FarmerProfileUpdate
from app.services.chatbot_service import ChatbotService


async def test_prompt_includes_identity_safety_and_farmer_context():
    gemini = AsyncMock()
    gemini.generate.return_value = "answer"
    farmer = FarmerContext(profile=FarmerProfileUpdate(preferred_language="Marathi"), crops=[])
    assert await ChatbotService(gemini).reply([], farmer, True) == "answer"
    prompt = gemini.generate.call_args.args[1]
    assert "ShetiSevek AI" in prompt
    assert "Marathi" in prompt
    assert "Never invent pesticide" in prompt
    assert "Google Search is available" in prompt
    assert "google_search_grounding" in prompt
