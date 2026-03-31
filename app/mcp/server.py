import json
import logging
from pathlib import Path

from fastmcp import FastMCP
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)

from app.config import settings

logger = logging.getLogger(__name__)

mcp = FastMCP("Multicard Docs")


def _get_state():
    from app.api.deps import get_app_state

    return get_app_state()


def _load_spec() -> dict:
    spec_path = Path(settings.app.docs_dir) / "docs.json"
    with open(spec_path) as f:
        return json.load(f)


@mcp.tool()
async def search_docs(query: str) -> str:
    """Search all indexed Multicard documentation for relevant information."""
    try:
        retriever = _get_state().index.as_retriever(similarity_top_k=5)
        nodes = await retriever.aretrieve(query)
        if not nodes:
            return "No results found."
        return "\n\n---\n\n".join(
            f"[{n.metadata.get('doc_type', 'unknown')}] {n.text[:500]}" for n in nodes
        )
    except Exception:
        logger.exception("search_docs failed")
        return "Error: search failed. Please try again."


@mcp.tool()
async def search_endpoints(query: str) -> str:
    """Search API endpoint definitions by semantic similarity."""
    try:
        retriever = _get_state().index.as_retriever(
            similarity_top_k=5,
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="doc_type", value="endpoint", operator=FilterOperator.EQ
                    )
                ]
            ),
        )
        nodes = await retriever.aretrieve(query)
        if not nodes:
            return "No endpoint results found."
        return "\n\n---\n\n".join(
            f"[{n.metadata.get('method', '')} {n.metadata.get('path', '')}] {n.text[:500]}"
            for n in nodes
        )
    except Exception:
        logger.exception("search_endpoints failed")
        return "Error: endpoint search failed. Please try again."


@mcp.tool()
async def get_endpoint(path: str, method: str) -> str:
    """Get the full JSON specification for a specific API endpoint."""
    spec = _load_spec()
    endpoint = spec.get("paths", {}).get(path, {}).get(method.lower())
    if endpoint:
        return json.dumps(endpoint, ensure_ascii=False, indent=2)
    return f"Endpoint {method.upper()} {path} not found."


@mcp.tool()
async def list_api_endpoints(tag: str = "") -> str:
    """List all available API endpoints with their summaries, optionally filtered by tag."""
    spec = _load_spec()
    results: list[str] = []
    for ep_path, methods in spec.get("paths", {}).items():
        for ep_method, details in methods.items():
            if ep_method not in ("get", "post", "put", "patch", "delete"):
                continue
            tags = details.get("tags", [])
            if tag and tag not in tags:
                continue
            results.append(
                f"{ep_method.upper()} {ep_path} — {details.get('summary', '')}"
            )
    return "\n".join(results) if results else "No endpoints found."


@mcp.tool()
async def ask_multicard(question: str, session_id: str = "mcp_default") -> str:
    """Ask the Multicard documentation assistant a question using the full agent."""
    try:
        state = _get_state()
        memory = state.get_memory(session_id)
        handler = state.agent.run(user_msg=question, memory=memory)
        result = await handler
        return str(result.response)
    except Exception:
        logger.exception("ask_multicard failed")
        return "Error: failed to process question. Please try again."
