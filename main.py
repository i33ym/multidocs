import logging
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic.warnings import PydanticDeprecatedSince20, PydanticDeprecatedSince211

warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince211)

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.deps import init_app_state
from app.api.router import router as api_router
from app.config import settings
from app.database import close_db, init_db
from app.mcp.server import mcp
from app.telegram.webhook import (
    router as telegram_router,
    start_telegram,
    stop_telegram,
)

logging.basicConfig(
    level=logging.DEBUG if settings.app.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    init_app_state()
    await start_telegram()
    logger.info("Application started")
    yield
    await stop_telegram()
    await close_db()
    logger.info("Application stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.allowed_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(telegram_router)


class MCPAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path.startswith("/mcp"):
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {settings.mcp.api_key}":
                return Response(status_code=401, content="Unauthorized")
        return await call_next(request)


app.add_middleware(MCPAuthMiddleware)
app.mount("/mcp", mcp.http_app())

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        ws="wsproto",
    )
