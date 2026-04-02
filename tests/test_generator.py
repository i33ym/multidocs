import ast
import json
import shutil
from pathlib import Path

from app.generator.codegen import generate_mcp_server

SAMPLE_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Test API", "version": "1.0.0", "description": "A test API"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/auth": {
            "post": {
                "summary": "Authenticate",
                "tags": ["Auth"],
                "parameters": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"key": {"type": "string"}},
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/users": {
            "get": {
                "summary": "List users",
                "tags": ["Users"],
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create user",
                "tags": ["Users"],
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/users/{id}": {
            "get": {
                "summary": "Get user",
                "tags": ["Users"],
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "summary": "Delete user",
                "tags": ["Users"],
                "responses": {"204": {"description": "Deleted"}},
            },
        },
    },
}

OUTPUT_DIR = Path("generated/_test")


def setup_function():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


def teardown_function():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


def test_generates_valid_python():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    code = (server_dir / "server.py").read_text()
    ast.parse(code)


def test_generates_all_files():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    assert (server_dir / "server.py").exists()
    assert (server_dir / "spec.json").exists()
    assert (server_dir / "mcp_config.json").exists()
    assert (server_dir / "README.md").exists()


def test_spec_preserved():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    stored = json.loads((server_dir / "spec.json").read_text())
    assert stored["info"]["title"] == "Test API"
    assert "/auth" in stored["paths"]


def test_mcp_config_valid():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    config = json.loads((server_dir / "mcp_config.json").read_text())
    assert "mcpServers" in config
    server_cfg = list(config["mcpServers"].values())[0]
    assert server_cfg["type"] == "stdio"
    assert "server.py" in server_cfg["args"][-1]


def test_tool_per_endpoint():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    code = (server_dir / "server.py").read_text()
    assert "async def post_auth" in code
    assert "async def get_users" in code
    assert "async def post_users" in code
    assert "async def get_users_2" in code  # dedup for /users/{id} GET
    assert "async def delete_users" in code


def test_deterministic():
    dir1 = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    code1 = (dir1 / "server.py").read_text()

    shutil.rmtree(OUTPUT_DIR)

    dir2 = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    code2 = (dir2 / "server.py").read_text()

    assert code1 == code2


def test_builtin_tools_present():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    code = (server_dir / "server.py").read_text()
    assert "async def list_endpoints" in code
    assert "async def get_api_info" in code
    assert "async def get_full_spec" in code


def test_readme_lists_all_tools():
    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)
    readme = (server_dir / "README.md").read_text()
    assert "post_auth" in readme
    assert "get_users" in readme
    assert "delete_users" in readme
