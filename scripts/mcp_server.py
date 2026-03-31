import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic.warnings import PydanticDeprecatedSince20, PydanticDeprecatedSince211

warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince211)

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncGenerator[None, None]:
    from app.api.deps import init_app_state
    from app.database import close_db, init_db

    await init_db()
    init_app_state()
    logger.info("MCP server ready")
    yield
    await close_db()


from app.mcp.server import mcp

mcp._lifespan = lifespan


if __name__ == "__main__":
    mcp.run(transport="stdio")
