import ast
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from app.generator.codegen import generate_mcp_server

OUTPUT_DIR = Path("generated/_eval_test")

SAMPLE_SPEC = {
    "openapi": "3.0.1",
    "info": {
        "title": "Eval Test API",
        "version": "2.0.0",
        "description": "API for evaluation testing",
    },
    "servers": [
        {"url": "https://api.example.com"},
        {"url": "https://staging.example.com"},
    ],
    "paths": {
        "/auth": {
            "post": {
                "summary": "Authenticate",
                "description": "Get an access token",
                "tags": ["Auth"],
                "parameters": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "password": {"type": "string"},
                                },
                                "required": ["username", "password"],
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Token response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"token": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "401": {"description": "Invalid credentials"},
                },
            }
        },
        "/users": {
            "get": {
                "summary": "List users",
                "tags": ["Users"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Max results",
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create user",
                "tags": ["Users"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string", "format": "email"},
                                },
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/users/{id}": {
            "get": {
                "summary": "Get user by ID",
                "tags": ["Users"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "summary": "Delete user",
                "tags": ["Users"],
                "responses": {"204": {"description": "Deleted"}},
            },
        },
        "/health": {
            "get": {
                "summary": "Health check",
                "tags": ["System"],
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}


@pytest.fixture(scope="module")
def generated_server():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    server_dir = generate_mcp_server(SAMPLE_SPEC, OUTPUT_DIR)

    spec = importlib.util.spec_from_file_location(
        "eval_server", server_dir / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_server"] = module
    spec.loader.exec_module(module)

    yield module

    del sys.modules["eval_server"]
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


# ==================================================================================== #
# TOOL OUTPUT EVALUATIONS
# ==================================================================================== #


async def test_list_endpoints_returns_all(generated_server):
    result = await generated_server.list_endpoints()
    assert "POST /auth" in result
    assert "GET /users" in result
    assert "POST /users" in result
    assert "GET /users/{id}" in result
    assert "DELETE /users/{id}" in result
    assert "GET /health" in result


async def test_list_endpoints_filter_by_tag(generated_server):
    result = await generated_server.list_endpoints(tag="Auth")
    assert "POST /auth" in result
    assert "/users" not in result


async def test_list_endpoints_filter_no_match(generated_server):
    result = await generated_server.list_endpoints(tag="NonExistent")
    assert result == "No endpoints found."


async def test_get_api_info_structure(generated_server):
    result = await generated_server.get_api_info()
    info = json.loads(result)

    assert info["title"] == "Eval Test API"
    assert info["version"] == "2.0.0"
    assert info["description"] == "API for evaluation testing"
    assert len(info["servers"]) == 2
    assert info["servers"][0]["url"] == "https://api.example.com"
    assert info["total_endpoints"] == 6


async def test_get_full_spec_is_valid_openapi(generated_server):
    result = await generated_server.get_full_spec()
    spec = json.loads(result)

    assert spec["openapi"] == "3.0.1"
    assert "paths" in spec
    assert "/auth" in spec["paths"]


async def test_endpoint_tool_returns_valid_json(generated_server):
    result = await generated_server.post_auth()
    data = json.loads(result)

    assert data["method"] == "POST"
    assert data["path"] == "/auth"


async def test_endpoint_tool_has_parameters(generated_server):
    result = await generated_server.get_users()
    data = json.loads(result)

    assert data["method"] == "GET"
    assert data["path"] == "/users"
    assert len(data["parameters"]) == 2
    param_names = {p["name"] for p in data["parameters"]}
    assert param_names == {"limit", "offset"}


async def test_endpoint_tool_has_request_body(generated_server):
    result = await generated_server.post_auth()
    data = json.loads(result)

    assert data["requestBody"] is not None
    schema = data["requestBody"]["content"]["application/json"]["schema"]
    assert "username" in schema["properties"]
    assert "password" in schema["properties"]
    assert schema["required"] == ["username", "password"]


async def test_endpoint_tool_has_responses(generated_server):
    result = await generated_server.post_auth()
    data = json.loads(result)

    assert "200" in data["responses"]
    assert "401" in data["responses"]


async def test_endpoint_tool_has_summary_and_tags(generated_server):
    result = await generated_server.post_auth()
    data = json.loads(result)

    assert data["summary"] == "Authenticate"
    assert data["description"] == "Get an access token"
    assert data["tags"] == ["Auth"]


async def test_deduped_tool_names_work(generated_server):
    result1 = await generated_server.get_users()
    result2 = await generated_server.get_users_2()

    data1 = json.loads(result1)
    data2 = json.loads(result2)

    assert data1["path"] == "/users"
    assert data2["path"] == "/users/{id}"


async def test_delete_tool_works(generated_server):
    result = await generated_server.delete_users()
    data = json.loads(result)

    assert data["method"] == "DELETE"
    assert data["path"] == "/users/{id}"


async def test_all_tools_return_parseable_json(generated_server):
    tool_fns = [
        generated_server.post_auth,
        generated_server.get_users,
        generated_server.post_users,
        generated_server.get_users_2,
        generated_server.delete_users,
        generated_server.get_health,
        generated_server.list_endpoints,
        generated_server.get_api_info,
        generated_server.get_full_spec,
    ]
    for fn in tool_fns:
        result = await fn() if not fn.__name__ == "list_endpoints" else await fn()
        assert isinstance(result, str)
        assert len(result) > 0


# ==================================================================================== #
# GUARDRAILS
# ==================================================================================== #


def test_guardrail_empty_paths():
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Empty", "version": "1.0.0"},
        "paths": {},
    }
    out = Path("generated/_guard_empty")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "async def list_endpoints" in code
        assert "async def get_api_info" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_special_chars_in_path():
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Special Chars", "version": "1.0.0"},
        "paths": {
            "/api/v2/users-list/{user-id}/profile.json": {
                "get": {
                    "summary": "Get profile",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    out = Path("generated/_guard_special")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "async def get_api_v2_users_list_profile_json" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_numeric_path_start():
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Numeric", "version": "1.0.0"},
        "paths": {
            "/2fa/verify": {
                "post": {
                    "summary": "Verify 2FA",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    out = Path("generated/_guard_numeric")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "async def post_2fa_verify" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_unicode_in_spec():
    spec = {
        "openapi": "3.0.1",
        "info": {
            "title": "Юникод API",
            "version": "1.0.0",
            "description": "Описание на русском",
        },
        "paths": {
            "/auth": {
                "post": {
                    "summary": "Авторизация",
                    "description": "Получение токена доступа",
                    "tags": ["Авторизация"],
                    "responses": {"200": {"description": "Успешно"}},
                }
            }
        },
    }
    out = Path("generated/_guard_unicode")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "Авторизация" in code
        assert "Получение токена доступа" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_many_duplicate_paths():
    paths = {}
    for i in range(5):
        paths[f"/items/{{{f'id{i}'}}}"] = {
            "get": {
                "summary": f"Get item variant {i}",
                "responses": {"200": {"description": "OK"}},
            }
        }
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Dupes", "version": "1.0.0"},
        "paths": paths,
    }
    out = Path("generated/_guard_dupes")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "async def get_items" in code
        assert "async def get_items_2" in code
        assert "async def get_items_3" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_large_spec():
    paths = {}
    for i in range(100):
        paths[f"/resource_{i}"] = {
            "get": {
                "summary": f"Get resource {i}",
                "tags": [f"Group{i % 5}"],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": f"Create resource {i}",
                "responses": {"201": {"description": "Created"}},
            },
        }
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Large API", "version": "1.0.0"},
        "paths": paths,
    }
    out = Path("generated/_guard_large")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)

        fn_count = code.count("async def ")
        assert (
            fn_count == 200 + 3
        )  # 200 endpoints + list_endpoints + get_api_info + get_full_spec
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_no_info():
    spec = {
        "openapi": "3.0.1",
        "paths": {
            "/ping": {
                "get": {"summary": "Ping", "responses": {"200": {"description": "OK"}}}
            }
        },
    }
    out = Path("generated/_guard_noinfo")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_triple_quotes_in_summary():
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Quotes", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Get \"test\" data with 'quotes'",
                    "description": "Description with\nnewlines\nand\ttabs",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    out = Path("generated/_guard_quotes")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
    finally:
        if out.exists():
            shutil.rmtree(out)


def test_guardrail_empty_summary_and_description():
    spec = {
        "openapi": "3.0.1",
        "info": {"title": "Minimal", "version": "1.0.0"},
        "paths": {"/bare": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    out = Path("generated/_guard_bare")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)
        assert "async def get_bare" in code
    finally:
        if out.exists():
            shutil.rmtree(out)


# ==================================================================================== #
# REAL SPEC EVALUATION
# ==================================================================================== #


def test_real_multicard_spec_generates():
    spec_path = Path("docs/docs.json")
    if not spec_path.exists():
        pytest.skip("docs/docs.json not found")

    spec = json.loads(spec_path.read_text())
    out = Path("generated/_eval_real")
    try:
        server_dir = generate_mcp_server(spec, out)
        code = (server_dir / "server.py").read_text()
        ast.parse(code)

        endpoint_count = sum(
            1
            for methods in spec["paths"].values()
            for m in methods
            if m in ("get", "post", "put", "patch", "delete")
        )
        fn_count = code.count("async def ") - 3  # minus builtins
        assert fn_count == endpoint_count
    finally:
        if out.exists():
            shutil.rmtree(out)
