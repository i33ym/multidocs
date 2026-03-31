import asyncio
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AppState, get_app_state
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    ReindexResponse,
)
from app.config import settings
from app.database import async_session
from app.indexing.pipeline import run_indexing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_rate_limits: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key: str) -> None:
    now = time.monotonic()
    window = _rate_limits[key]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= settings.app.rate_limit_rpm:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def _require_admin(request: Request) -> None:
    if not settings.app.admin_api_key:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {settings.app.admin_api_key}":
        raise HTTPException(status_code=401, detail="Invalid admin credentials")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = "ok"
    try:
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    openai_status = "ok"
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai.api_key)
        await client.models.retrieve(settings.openai.model)
    except Exception:
        openai_status = "error"

    status = "ok" if db_status == "ok" and openai_status == "ok" else "degraded"
    return HealthResponse(status=status, database=db_status, openai=openai_status)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def chat(
    request: ChatRequest, state: AppState = Depends(get_app_state)
) -> ChatResponse:
    _check_rate_limit(f"chat:{request.session_id}")
    try:
        memory = state.get_memory(request.session_id)
        handler = state.agent.run(user_msg=request.message, memory=memory)
        response = await asyncio.wait_for(
            handler, timeout=settings.app.agent_timeout
        )
        return ChatResponse(
            response=str(response.response), session_id=request.session_id
        )
    except asyncio.TimeoutError:
        logger.error("Agent timed out for session %s", request.session_id)
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception:
        logger.exception("Chat error for session %s", request.session_id)
        raise HTTPException(status_code=500, detail="Failed to generate response")


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest, state: AppState = Depends(get_app_state)
) -> StreamingResponse:
    _check_rate_limit(f"chat:{request.session_id}")

    async def generate():
        from llama_index.core.agent.workflow import AgentStream

        try:
            memory = state.get_memory(request.session_id)
            handler = state.agent.run(user_msg=request.message, memory=memory)
            async for event in handler.stream_events():
                if isinstance(event, AgentStream) and event.delta:
                    yield event.delta
        except asyncio.TimeoutError:
            yield "\n\n[Error: Request timed out]"
        except Exception:
            logger.exception("Stream error for session %s", request.session_id)
            yield "\n\n[Error: Failed to generate response]"

    return StreamingResponse(generate(), media_type="text/plain")


@router.post(
    "/admin/reindex",
    response_model=ReindexResponse,
    dependencies=[Depends(_require_admin)],
)
async def reindex(state: AppState = Depends(get_app_state)) -> ReindexResponse:
    try:
        count = await run_indexing(state.index, force=True)
        logger.info("Reindexed %d nodes", count)
        return ReindexResponse(status="ok", nodes_indexed=count)
    except Exception:
        logger.exception("Reindex failed")
        raise HTTPException(status_code=500, detail="Reindex failed")
