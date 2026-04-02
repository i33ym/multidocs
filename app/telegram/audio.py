import logging
import tempfile
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram.bot_token}"


async def transcribe_voice(file_id: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TELEGRAM_API}/getFile", params={"file_id": file_id}
            )
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Failed to get file info: %s", data)
                return None

            file_path = data["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{settings.telegram.bot_token}/{file_path}"

            audio_resp = await client.get(file_url)
            audio_resp.raise_for_status()

        suffix = Path(file_path).suffix or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_resp.content)
            tmp_path = Path(tmp.name)

        try:
            openai_client = AsyncOpenAI(api_key=settings.openai.api_key)
            with open(tmp_path, "rb") as audio_file:
                transcript = await openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return transcript.text
        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception:
        logger.exception("Failed to transcribe voice message %s", file_id)
        return None
