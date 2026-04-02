import asyncio
import hmac
import logging

import httpx
from fastapi import APIRouter, Request, Response

from app.agent.prompts import TELEGRAM_CONTEXT_TEMPLATE
from app.api.deps import get_app_state
from app.config import settings
from app.telegram.audio import transcribe_voice
from app.telegram.formatter import to_telegram_html, truncate_message
from app.telegram.handlers import get_chat_context, should_respond, store_message

logger = logging.getLogger(__name__)

router = APIRouter()

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram.bot_token}"

_polling_task: asyncio.Task[None] | None = None


async def _send_reply(chat_id: int, text: str, reply_to: int) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_to_message_id": reply_to,
            },
        )


async def _send_typing(chat_id: int) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
        )


def _extract_text_and_file_id(message: dict) -> tuple[str | None, str | None]:
    if message.get("text"):
        return message["text"], None

    voice = message.get("voice") or message.get("audio")
    if voice:
        caption = message.get("caption", "")
        return caption or None, voice["file_id"]

    return None, None


async def _handle_message(message: dict) -> None:
    chat_id: int = message["chat"]["id"]
    chat_type: str = message["chat"].get("type", "private")
    user_id: int = message["from"]["id"]
    username: str | None = message["from"].get("username")
    message_id: int = message["message_id"]

    text, voice_file_id = _extract_text_and_file_id(message)

    if voice_file_id:
        try:
            await _send_typing(chat_id)
        except Exception:
            pass

        transcribed = await transcribe_voice(voice_file_id)
        if transcribed:
            text = f"[Voice message] {transcribed}"
            logger.info("Transcribed voice in chat %d: %s", chat_id, text[:100])
        else:
            try:
                await _send_reply(
                    chat_id, "Sorry, I couldn't process that voice message.", message_id
                )
            except Exception:
                pass
            return

    if not text:
        return

    try:
        await store_message(chat_id, user_id, username, text)
    except Exception:
        logger.exception("Failed to store message in chat %d", chat_id)

    if not should_respond(text, chat_type):
        return

    try:
        await _send_typing(chat_id)
    except Exception:
        pass

    try:
        state = get_app_state()
        memory = state.get_memory(f"tg_{chat_id}")

        context = await get_chat_context(chat_id)
        user_message = TELEGRAM_CONTEXT_TEMPLATE.format(context=context, message=text)

        handler = state.agent.run(user_msg=user_message, memory=memory)
        result = await asyncio.wait_for(handler, timeout=settings.app.agent_timeout)
        response_text = truncate_message(
            to_telegram_html(str(getattr(result, "response", result)))
        )
    except asyncio.TimeoutError:
        logger.error("Agent timed out for Telegram chat %d", chat_id)
        response_text = "Sorry, the request timed out. Please try again."
    except Exception:
        logger.exception("Agent error for Telegram chat %d", chat_id)
        response_text = "Sorry, something went wrong. Please try again."

    try:
        await _send_reply(chat_id, response_text, message_id)
    except Exception:
        logger.exception("Failed to send Telegram reply to chat %d", chat_id)


async def _poll_loop() -> None:
    offset: int = 0
    logger.info("Telegram polling started")
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        while True:
            try:
                resp = await client.get(
                    f"{TELEGRAM_API}/getUpdates",
                    params={
                        "offset": offset,
                        "timeout": 30,
                        "allowed_updates": ["message"],
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram getUpdates error: %s", data)
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        asyncio.create_task(_handle_message(update["message"]))

            except asyncio.CancelledError:
                logger.info("Telegram polling stopped")
                return
            except Exception:
                logger.exception("Telegram polling error")
                await asyncio.sleep(5)


async def start_telegram() -> None:
    global _polling_task

    if settings.telegram.mode == "webhook":
        if not settings.telegram.webhook_url:
            logger.warning(
                "TELEGRAM_WEBHOOK_URL not set, skipping webhook registration"
            )
            return
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{TELEGRAM_API}/setWebhook",
                    json={
                        "url": settings.telegram.webhook_url,
                        "secret_token": settings.telegram.webhook_secret,
                        "allowed_updates": ["message"],
                    },
                )
                data = resp.json()
                if data.get("ok"):
                    logger.info(
                        "Telegram webhook registered: %s",
                        settings.telegram.webhook_url,
                    )
                else:
                    logger.warning("Telegram webhook registration failed: %s", data)
        except Exception:
            logger.exception("Failed to register Telegram webhook")
    else:
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELEGRAM_API}/deleteWebhook")
        _polling_task = asyncio.create_task(_poll_loop())


async def stop_telegram() -> None:
    global _polling_task
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> Response:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.telegram.webhook_secret or not hmac.compare_digest(
        secret, settings.telegram.webhook_secret
    ):
        return Response(status_code=403)

    data = await request.json()
    message = data.get("message")
    if message:
        await _handle_message(message)

    return Response(status_code=200)
