from sqlalchemy import delete, func, select

from app.config import settings
from app.database import async_session
from app.models import TelegramMessage


async def store_message(
    chat_id: int, user_id: int, username: str | None, text: str
) -> None:
    async with async_session() as session:
        session.add(
            TelegramMessage(
                chat_id=chat_id, user_id=user_id, username=username, text=text
            )
        )
        await session.flush()

        count_result = await session.execute(
            select(func.count())
            .select_from(TelegramMessage)
            .where(TelegramMessage.chat_id == chat_id)
        )
        total = count_result.scalar_one()

        if total > settings.memory.chat_history_limit:
            excess = total - settings.memory.chat_history_limit
            oldest = await session.execute(
                select(TelegramMessage.id)
                .where(TelegramMessage.chat_id == chat_id)
                .order_by(TelegramMessage.created_at.asc())
                .limit(excess)
            )
            ids_to_delete = [row[0] for row in oldest.all()]
            if ids_to_delete:
                await session.execute(
                    delete(TelegramMessage).where(TelegramMessage.id.in_(ids_to_delete))
                )

        await session.commit()


def should_respond(text: str, chat_type: str) -> bool:
    if chat_type == "private":
        return True
    return f"@{settings.telegram.bot_username}" in text


async def get_chat_context(chat_id: int, limit: int = 20) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(TelegramMessage)
            .where(TelegramMessage.chat_id == chat_id)
            .order_by(TelegramMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))

    return "\n".join(f"{msg.username or msg.user_id}: {msg.text}" for msg in messages)
