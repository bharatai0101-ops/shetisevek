import json

from app.integrations.gemini.service import GeminiService
from app.prompts.shetisevek import SYSTEM_PROMPT
from app.schemas.farmer import FarmerContext
from app.schemas.message import HistoryMessage


class ChatbotService:
    def __init__(self, gemini: GeminiService) -> None:
        self.gemini = gemini

    async def reply(
        self,
        history: list[HistoryMessage],
        farmer: FarmerContext,
        new_conversation: bool,
        command_result: str | None = None,
    ) -> str:
        context = json.dumps(
            {
                "farmer": farmer.model_dump(mode="json", exclude_none=True),
                "new_conversation": new_conversation,
                "command_result": command_result,
                "connected_capabilities": [
                    "text_conversation",
                    "explicit_profile_and_crop_storage",
                ],
            },
            ensure_ascii=False,
        )
        return await self.gemini.generate(history, SYSTEM_PROMPT + "\nContext data:\n" + context)
