import asyncio
import logging
import signal
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import make_engine
from app.integrations.gemini.client import create_gemini_client
from app.integrations.gemini.service import GeminiService
from app.integrations.whatsapp.client import WhatsAppClient
from app.services.chatbot_service import ChatbotService
from app.workers.job_service import JobService
from app.workers.processor import Processor

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    gemini = create_gemini_client(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            processor = Processor(
                settings,
                ChatbotService(GeminiService(gemini, settings)),
                WhatsAppClient(http, settings),
            )
            jobs = JobService(engine, processor, str(uuid4()))
            while not stop.is_set():
                try:
                    worked = await jobs.tick()
                    # Liveness artifact only; PostgreSQL remains the source of job truth.
                    heartbeat = Path(tempfile.gettempdir()) / "shetisevek-worker-heartbeat"
                    await asyncio.to_thread(heartbeat.touch)
                except Exception:
                    logger.error(
                        "worker_iteration_failed", extra={"error_code": "database_or_internal"}
                    )
                    worked = False
                if not worked:
                    try:
                        await asyncio.wait_for(stop.wait(), settings.job_poll_interval_seconds)
                    except asyncio.TimeoutError:
                        pass
    finally:
        await gemini.aio.aclose()
        gemini.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
