import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.deps import init_app_state
from app.database import close_db, init_db
from app.indexing.pipeline import run_indexing


async def main() -> None:
    await init_db()
    state = init_app_state()
    count = await run_indexing(state.index)
    print(f"Indexed {count} nodes")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
