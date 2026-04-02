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

    tags_by_endpoint: dict[str, list[str]] = {}
    for ep_path, methods in openapi_spec.get("paths", {}).items():
        for ep_method, details in methods.items():
            if ep_method in ("get", "post", "put", "patch", "delete"):
                for tag in details.get("tags", []):
                    tags_by_endpoint.setdefault(tag, []).append(
                        f"{ep_method.upper()} {ep_path}"
                    )

    async def search_docs(query: str) -> str:
        """Semantic search across ALL indexed documentation (guides + endpoints).
        Use this for broad questions or when you're unsure which type of content to search.
        Returns the top 5 most relevant chunks with their doc_type labels."""
        retriever = index.as_retriever(similarity_top_k=5)
        nodes = await retriever.aretrieve(query)
        if not nodes:
            return (
                "No results found. Try rephrasing your query with different keywords."
            )
        return "\n\n---\n\n".join(
            f"[{n.metadata.get('doc_type', 'unknown')}] "
            f"(score: {n.score:.3f}) {n.text[:800]}"
            for n in nodes
        )

    async def search_endpoints(query: str) -> str:
        """Semantic search filtered to API endpoint definitions only.
        Use this when looking for a specific API method or operation.
        Returns endpoint path, method, and specification excerpt."""
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
            return (
                "No endpoint results found. "
                "Try using list_endpoints or search_by_tag to discover available endpoints."
            )
        return "\n\n---\n\n".join(
            f"[{n.metadata.get('method', '')} {n.metadata.get('path', '')}] "
            f"(score: {n.score:.3f}) {n.text[:800]}"
            for n in nodes
        )

    async def search_guides(query: str) -> str:
        """Semantic search filtered to markdown guides and general documentation.
        Use this for integration patterns, error handling, authentication flows,
        and general concepts that aren't tied to a specific endpoint."""
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
            return "No guide results found. Try search_docs for a broader search."
        return "\n\n---\n\n".join(
            f"(score: {n.score:.3f}) {n.text[:800]}" for n in nodes
        )

    async def get_endpoint_details(path: str, method: str) -> str:
        """Get the COMPLETE JSON specification for a specific API endpoint.
        You MUST call this before showing any endpoint parameters, request body,
        or response format to the user. Returns the full OpenAPI definition including
        parameters, requestBody schema, response schemas, and examples.
        Args: path (e.g. '/auth', '/payment/invoice'), method (e.g. 'post', 'get')"""
        endpoint = openapi_spec.get("paths", {}).get(path, {}).get(method.lower())
        if endpoint:
            return json.dumps(endpoint, ensure_ascii=False, indent=2)
        available = [
            f"{m.upper()} {p}"
            for p, methods in openapi_spec.get("paths", {}).items()
            for m in methods
            if m in ("get", "post", "put", "patch", "delete")
        ]
        return (
            f"Endpoint {method.upper()} {path} not found. "
            f"Available endpoints:\n" + "\n".join(available[:20])
        )

    async def list_endpoints(tag: str = "") -> str:
        """List all available API endpoints with their summaries.
        Call this first to understand what the API offers.
        Optionally filter by tag name (e.g. 'Авторизация', 'Холдирование').
        Returns: method, path, summary, and tags for each endpoint."""
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

    async def search_by_tag(tag: str) -> str:
        """Find all endpoints belonging to a specific API tag/category.
        Available tags: Авторизация, Оплата на платежной странице Multicard,
        Привязка карт (форма), Привязка карт (API), Оплата на странице Партнера,
        Холдирование, Выплаты на карту (payouts), Дополнительные методы.
        Returns all endpoints in that category with summaries."""
        matching_tags = [t for t in tags_by_endpoint if tag.lower() in t.lower()]
        if not matching_tags:
            available = "\n".join(f"- {t}" for t in sorted(tags_by_endpoint.keys()))
            return f"Tag '{tag}' not found. Available tags:\n{available}"

        results: list[str] = []
        for matched_tag in matching_tags:
            results.append(f"\n## {matched_tag}")
            for ep_path, methods in openapi_spec.get("paths", {}).items():
                for ep_method, details in methods.items():
                    if ep_method not in ("get", "post", "put", "patch", "delete"):
                        continue
                    if matched_tag in details.get("tags", []):
                        summary = details.get("summary", "")
                        results.append(f"  {ep_method.upper()} {ep_path} — {summary}")
        return "\n".join(results)

    return [
        FunctionTool.from_defaults(async_fn=search_docs, name="search_docs"),
        FunctionTool.from_defaults(async_fn=search_endpoints, name="search_endpoints"),
        FunctionTool.from_defaults(async_fn=search_guides, name="search_guides"),
        FunctionTool.from_defaults(
            async_fn=get_endpoint_details, name="get_endpoint_details"
        ),
        FunctionTool.from_defaults(async_fn=list_endpoints, name="list_endpoints"),
        FunctionTool.from_defaults(async_fn=search_by_tag, name="search_by_tag"),
    ]
