import hashlib
from pathlib import Path

from llama_index.core import VectorStoreIndex
from sqlalchemy import select, text

from app.config import settings
from app.database import async_session
from app.indexing.loader import get_splitter, load_documents
from app.models import IndexedFile


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _needs_indexing(docs_dir: Path) -> bool:
    all_files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.json"))

    async with async_session() as session:
        for file_path in all_files:
            checksum = _checksum(file_path)
            result = await session.execute(
                select(IndexedFile).where(IndexedFile.filename == str(file_path))
            )
            existing = result.scalar_one_or_none()
            if existing is None or existing.checksum != checksum:
                return True

    return False


async def _update_checksums(docs_dir: Path) -> None:
    all_files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.json"))

    async with async_session() as session:
        for file_path in all_files:
            checksum = _checksum(file_path)
            result = await session.execute(
                select(IndexedFile).where(IndexedFile.filename == str(file_path))
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.checksum = checksum
            else:
                session.add(IndexedFile(filename=str(file_path), checksum=checksum))

        await session.commit()


async def run_indexing(index: VectorStoreIndex, force: bool = False) -> int:
    docs_dir = Path(settings.app.docs_dir)

    if not force and not await _needs_indexing(docs_dir):
        return 0

    documents = load_documents(docs_dir)
    nodes = get_splitter().get_nodes_from_documents(documents)

    try:
        async with async_session() as session:
            await session.execute(text("DELETE FROM data_document_embeddings"))
            await session.commit()
    except Exception:
        pass

    index.insert_nodes(nodes)
    await _update_checksums(docs_dir)

    return len(nodes)
