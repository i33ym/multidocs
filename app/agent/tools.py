import json
from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.tools import BaseTool, FunctionTool
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)


def create_tools(index: VectorStoreIndex, spec_path: Path) -> list[BaseTool]:
    with open(spec_path) as f:
        openapi_spec = json.load(f)

    async def search_docs(query: str) -> str:
        """Search all indexed documentation for relevant information about the Multicard API."""
        retriever = index.as_retriever(similarity_top_k=5)
        nodes = await retriever.aretrieve(query)
        if not nodes:
            return "No results found."
        return "\n\n---\n\n".join(
            f"[{n.metadata.get('doc_type', 'unknown')}] {n.text[:500]}" for n in nodes
        )

    async def search_endpoints(query: str) -> str:
        """Search API endpoint definitions by semantic similarity. Use for finding specific API methods."""
        retriever = index.as_retriever(
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

    async def search_guides(query: str) -> str:
        """Search markdown guides and general documentation about the Multicard platform."""
        retriever = index.as_retriever(
            similarity_top_k=5,
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="doc_type", value="guide", operator=FilterOperator.EQ
                    )
                ]
            ),
        )
        nodes = await retriever.aretrieve(query)
        if not nodes:
            return "No guide results found."
        return "\n\n---\n\n".join(n.text[:500] for n in nodes)

    async def get_endpoint_details(path: str, method: str) -> str:
        """Get the full JSON specification for a specific API endpoint by its path and HTTP method."""
        endpoint = openapi_spec.get("paths", {}).get(path, {}).get(method.lower())
        if endpoint:
            return json.dumps(endpoint, ensure_ascii=False, indent=2)
        return f"Endpoint {method.upper()} {path} not found."

    async def list_endpoints(tag: str = "") -> str:
        """List all available API endpoints with their summaries. Optionally filter by tag name."""
        results: list[str] = []
        for ep_path, methods in openapi_spec.get("paths", {}).items():
            for ep_method, details in methods.items():
                if ep_method not in ("get", "post", "put", "patch", "delete"):
                    continue
                tags = details.get("tags", [])
                if tag and tag not in tags:
                    continue
                summary = details.get("summary", "")
                results.append(
                    f"{ep_method.upper()} {ep_path} — {summary} [{', '.join(tags)}]"
                )
        return "\n".join(results) if results else "No endpoints found."

    return [
        FunctionTool.from_defaults(async_fn=search_docs, name="search_docs"),
        FunctionTool.from_defaults(async_fn=search_endpoints, name="search_endpoints"),
        FunctionTool.from_defaults(async_fn=search_guides, name="search_guides"),
        FunctionTool.from_defaults(
            async_fn=get_endpoint_details, name="get_endpoint_details"
        ),
        FunctionTool.from_defaults(async_fn=list_endpoints, name="list_endpoints"),
    ]
