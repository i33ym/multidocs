import asyncio
import logging
import time
from collections import defaultdict
from pathlib import Path

import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import AppState, get_app_state
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    ErrorResponse,
    GenerateResponse,
    GeneratedServer,
    GeneratedServerList,
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
        result = await asyncio.wait_for(handler, timeout=settings.app.agent_timeout)
        return ChatResponse(
            response=str(getattr(result, "response", result)),
            session_id=request.session_id,
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


@router.post("/transcribe")
async def transcribe(file: UploadFile) -> dict[str, str]:
    _check_rate_limit(f"transcribe:{file.filename}")
    try:
        from openai import AsyncOpenAI

        content = await file.read()
        suffix = Path(file.filename or "audio.webm").suffix or ".webm"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            client = AsyncOpenAI(api_key=settings.openai.api_key)
            with open(tmp_path, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return {"text": transcript.text}
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed")


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


GENERATED_DIR = Path(__file__).resolve().parent.parent.parent / "generated"


def _read_server_info(server_dir: Path) -> GeneratedServer:
    import json as _json

    spec = _json.loads((server_dir / "spec.json").read_text())
    config = _json.loads((server_dir / "mcp_config.json").read_text())
    info = spec.get("info", {})
    endpoint_count = sum(
        1
        for methods in spec.get("paths", {}).values()
        for m in methods
        if m in ("get", "post", "put", "patch", "delete")
    )
    return GeneratedServer(
        name=server_dir.name,
        title=info.get("title", ""),
        version=info.get("version", ""),
        endpoints=endpoint_count,
        path=str(server_dir),
        mcp_config=config,
    )


@router.post(
    "/admin/specs",
    response_model=GenerateResponse,
    dependencies=[Depends(_require_admin)],
)
async def upload_spec(request: Request) -> GenerateResponse:
    content_type = request.headers.get("content-type", "")

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("file")
            if upload is None:
                raise HTTPException(status_code=400, detail="No file uploaded")
            raw = await upload.read()
            filename = getattr(upload, "filename", "spec")
        else:
            raw = await request.body()
            filename = "spec"

        text = raw.decode("utf-8")

        if filename.endswith((".yaml", ".yml")) or text.strip().startswith(
            ("openapi:", "swagger:")
        ):
            import yaml

            spec = yaml.safe_load(text)
        else:
            import json as _json

            spec = _json.loads(text)

        if not isinstance(spec, dict) or "paths" not in spec:
            raise HTTPException(
                status_code=400, detail="Invalid OpenAPI spec: missing 'paths'"
            )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to parse uploaded spec")
        raise HTTPException(status_code=400, detail="Failed to parse spec file")

    try:
        from app.generator.codegen import generate_mcp_server

        server_dir = generate_mcp_server(spec, GENERATED_DIR)
        server_info = _read_server_info(server_dir)
        logger.info(
            "Generated MCP server: %s (%d endpoints)",
            server_info.name,
            server_info.endpoints,
        )
        return GenerateResponse(status="ok", server=server_info)
    except Exception:
        logger.exception("Code generation failed")
        raise HTTPException(status_code=500, detail="Code generation failed")


@router.get(
    "/admin/specs",
    response_model=GeneratedServerList,
    dependencies=[Depends(_require_admin)],
)
async def list_specs() -> GeneratedServerList:
    servers: list[GeneratedServer] = []
    if GENERATED_DIR.exists():
        for d in sorted(GENERATED_DIR.iterdir()):
            if d.is_dir() and (d / "server.py").exists():
                try:
                    servers.append(_read_server_info(d))
                except Exception:
                    logger.warning("Skipping malformed server dir: %s", d.name)
    return GeneratedServerList(servers=servers)


@router.delete(
    "/admin/specs/{name}",
    response_model=DeleteResponse,
    dependencies=[Depends(_require_admin)],
)
async def delete_spec(name: str) -> DeleteResponse:
    server_dir = GENERATED_DIR / name
    if not server_dir.exists() or not server_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")

    import shutil

    shutil.rmtree(server_dir)
    logger.info("Deleted generated server: %s", name)
    return DeleteResponse(status="ok", deleted=name)
