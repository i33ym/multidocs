from pathlib import Path

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document

from app.indexing.parser import parse_openapi_spec


def load_documents(docs_dir: Path) -> list[Document]:
    documents: list[Document] = []

    for md_file in docs_dir.glob("*.md"):
        documents.append(
            Document(
                text=md_file.read_text(encoding="utf-8"),
                metadata={
                    "doc_type": "guide",
                    "source": str(md_file),
                    "filename": md_file.name,
                },
            )
        )

    for json_file in docs_dir.glob("*.json"):
        documents.extend(parse_openapi_spec(json_file))

    return documents


def get_splitter() -> SentenceSplitter:
    return SentenceSplitter(chunk_size=1024, chunk_overlap=200)
