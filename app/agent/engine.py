from collections.abc import Callable
from pathlib import Path
from typing import Any

from llama_index.core import VectorStoreIndex
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import BaseTool
from llama_index.core.memory import FactExtractionMemoryBlock, Memory, VectorMemoryBlock
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.postgres import PGVectorStore

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import create_tools
from app.config import settings


def create_llm() -> OpenAI:
    return OpenAI(api_key=settings.openai.api_key, model=settings.openai.model)


def create_embed_model() -> OpenAIEmbedding:
    return OpenAIEmbedding(
        api_key=settings.openai.api_key,
        model_name=settings.openai.embedding_model,
    )


def create_vector_store(table_name: str = "document_embeddings") -> PGVectorStore:
    db = settings.database
    sync_url = (
        f"postgresql+psycopg://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}"
    )
    return PGVectorStore(
        connection_string=sync_url,
        async_connection_string=db.async_url,
        table_name=table_name,
        embed_dim=1536,
        use_jsonb=True,
    )


def create_index(
    vector_store: PGVectorStore, embed_model: OpenAIEmbedding
) -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)


def create_memory(
    session_id: str,
    llm: OpenAI,
    embed_model: OpenAIEmbedding,
    memory_vector_store: PGVectorStore,
) -> Memory:
    return Memory.from_defaults(
        session_id=session_id,
        token_limit=settings.memory.token_limit,
        chat_history_token_ratio=0.7,
        memory_blocks=[
            FactExtractionMemoryBlock(llm=llm, max_facts=settings.memory.max_facts),
            VectorMemoryBlock(
                vector_store=memory_vector_store, embed_model=embed_model
            ),
        ],
        async_database_uri=settings.database.async_url,
    )


def create_agent(
    index: VectorStoreIndex, llm: OpenAI, spec_path: Path
) -> FunctionAgent:
    tools: list[BaseTool | Callable[..., Any]] = list(create_tools(index, spec_path))
    return FunctionAgent(
        tools=tools,
        llm=llm,
        system_prompt=SYSTEM_PROMPT,
    )
