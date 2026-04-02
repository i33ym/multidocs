import json
import re
from pathlib import Path


def _sanitize_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if name and name[0].isdigit():
        name = f"op_{name}"
    return name or "unnamed"


def _make_tool_name(method: str, path: str) -> str:
    parts = path.strip("/").split("/")
    clean = "_".join(p for p in parts if not p.startswith("{"))
    return _sanitize_name(f"{method}_{clean}")


def _make_docstring(method: str, path: str, details: dict) -> str:
    summary = details.get("summary", "").strip()
    description = details.get("description", "").strip()
    tags = details.get("tags", [])

    parts = [f"{method.upper()} {path}"]
    if summary:
        parts.insert(0, summary)
    if description and description != summary:
        parts.append(description)
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    return " — ".join(parts)


def _build_endpoint_payload(method: str, path: str, details: dict) -> dict:
    return {
        "method": method.upper(),
        "path": path,
        "summary": details.get("summary", ""),
        "description": details.get("description", ""),
        "tags": details.get("tags", []),
        "parameters": details.get("parameters", []),
        "requestBody": details.get("requestBody"),
        "responses": details.get("responses", {}),
        "security": details.get("security", []),
    }


def generate_mcp_server(spec: dict, output_dir: Path) -> Path:
    info = spec.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "1.0.0")
    api_description = info.get("description", "")
    servers = spec.get("servers", [])
    paths = spec.get("paths", {})

    safe_title = _sanitize_name(title)
    server_dir = output_dir / safe_title
    server_dir.mkdir(parents=True, exist_ok=True)

    spec_path = server_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2))

    tools_code: list[str] = []
    tool_names: set[str] = set()

    for path, methods in paths.items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            name = _make_tool_name(method, path)
            base_name = name
            counter = 2
            while name in tool_names:
                name = f"{base_name}_{counter}"
                counter += 1
            tool_names.add(name)

            docstring = _make_docstring(method, path, details)
            payload = _build_endpoint_payload(method, path, details)
            payload_str = json.dumps(json.dumps(payload, ensure_ascii=False, indent=2))

            tools_code.append(
                f"@mcp.tool()\n"
                f"async def {name}() -> str:\n"
                f'    """{docstring}"""\n'
                f"    return {payload_str}\n"
            )

    base_url_lines = ""
    if servers:
        urls = [s.get("url", "") for s in servers if s.get("url")]
        if urls:
            base_url_lines = f"BASE_URLS = {json.dumps(urls)}\n\n"

    all_endpoints: list[dict[str, str]] = []
    for path, methods in paths.items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            all_endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": details.get("summary", ""),
                    "tags": ", ".join(details.get("tags", [])),
                }
            )

    endpoints_json = json.dumps(all_endpoints, ensure_ascii=False, indent=2)

    server_code = f'''\
import json
from pathlib import Path

from fastmcp import FastMCP

SPEC_PATH = Path(__file__).parent / "spec.json"
{base_url_lines}
mcp = FastMCP("{title} v{version}")


@mcp.tool()
async def list_endpoints(tag: str = "") -> str:
    """List all available API endpoints. Optionally filter by tag name."""
    endpoints = {endpoints_json}
    if tag:
        endpoints = [e for e in endpoints if tag.lower() in e["tags"].lower()]
    lines = [f"{{e['method']}} {{e['path']}} — {{e['summary']}}" for e in endpoints]
    return "\\n".join(lines) if lines else "No endpoints found."


@mcp.tool()
async def get_api_info() -> str:
    """Get general API information: title, version, description, and base URLs."""
    return json.dumps(
        {{
            "title": {json.dumps(title)},
            "version": {json.dumps(version)},
            "description": {json.dumps(api_description)},
            "servers": {json.dumps(servers)},
            "total_endpoints": {len(all_endpoints)},
        }},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def get_full_spec() -> str:
    """Get the complete OpenAPI specification as JSON."""
    return SPEC_PATH.read_text(encoding="utf-8")


{"".join(tools_code)}

if __name__ == "__main__":
    mcp.run(transport="stdio")
'''

    server_path = server_dir / "server.py"
    server_path.write_text(server_code)

    mcp_config = {
        "mcpServers": {
            safe_title: {
                "type": "stdio",
                "command": "uv",
                "args": ["run", "python", str(server_path.resolve())],
                "cwd": str(Path.cwd()),
            }
        }
    }
    config_path = server_dir / "mcp_config.json"
    config_path.write_text(json.dumps(mcp_config, indent=2))

    readme_content = f"""\
# {title} MCP Server

Auto-generated MCP server from OpenAPI specification.

## Usage

### stdio (Claude Desktop / IDE)

Copy the contents of `mcp_config.json` into your MCP client config.

### Run directly

```bash
uv run python {server_path.name}
```

## Tools

| Tool | Description |
| ---- | ----------- |
| `list_endpoints` | List all API endpoints, filter by tag |
| `get_api_info` | API title, version, description, base URLs |
| `get_full_spec` | Complete OpenAPI spec as JSON |
"""

    for ep in all_endpoints:
        tool_name = _make_tool_name(ep["method"].lower(), ep["path"])
        readme_content += (
            f"| `{tool_name}` | {ep['summary']} — {ep['method']} {ep['path']} |\n"
        )

    readme_path = server_dir / "README.md"
    readme_path.write_text(readme_content)

    return server_dir
