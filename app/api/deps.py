from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.memory import Memory
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.postgres import PGVectorStore

from app.agent.engine import (
    create_agent,
    create_embed_model,
    create_index,
    create_llm,
    create_memory,
    create_vector_store,
)
from app.config import settings


class AppState:
    llm: OpenAI
    embed_model: OpenAIEmbedding
    vector_store: PGVectorStore
    memory_vector_store: PGVectorStore
    index: VectorStoreIndex
    agent: FunctionAgent

    def __init__(self) -> None:
        self.llm = create_llm()
        self.embed_model = create_embed_model()
        self.vector_store = create_vector_store()
        self.memory_vector_store = create_vector_store(table_name="memory_vectors")
        self.index = create_index(self.vector_store, self.embed_model)
        self.agent = create_agent(
            self.index, self.llm, Path(settings.app.docs_dir) / "docs.json"
        )

    def get_memory(self, session_id: str) -> Memory:
        return create_memory(
            session_id, self.llm, self.embed_model, self.memory_vector_store
        )


_app_state: AppState | None = None


def init_app_state() -> AppState:
    global _app_state
    _app_state = AppState()
    return _app_state


def get_app_state() -> AppState:
    assert _app_state is not None
    return _app_state
