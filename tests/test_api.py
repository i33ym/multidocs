from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


class FakeHandler:
    def __init__(self, response):
        self._response = response

    def __await__(self):
        async def _inner():
            return self._response

        return _inner().__await__()

    async def stream_events(self):
        return
        yield


@pytest.fixture
def mock_app_state():
    state = MagicMock()
    state.llm = MagicMock()
    state.embed_model = MagicMock()

    mock_response = MagicMock()
    mock_response.response = "Test response"

    state.agent.run.return_value = FakeHandler(mock_response)
    state.get_memory.return_value = MagicMock()
    return state


@pytest_asyncio.fixture
async def client(mock_app_state):
    with (
        patch("app.api.deps._app_state", mock_app_state),
        patch("app.database.init_db", new_callable=AsyncMock),
        patch("app.database.close_db", new_callable=AsyncMock),
        patch("app.telegram.webhook.start_telegram", new_callable=AsyncMock),
        patch("app.telegram.webhook.stop_telegram", new_callable=AsyncMock),
    ):
        from main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac


async def test_health(client):
    with patch("app.api.router.async_session") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session_factory.return_value = mock_session

        with patch("app.api.router.settings") as mock_settings:
            mock_settings.openai.api_key = "fake"
            mock_settings.openai.model = "gpt-4o-mini"

            resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")


async def test_chat(client):
    resp = await client.post(
        "/api/chat",
        json={"message": "hello", "session_id": "test-session"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test-session"
    assert data["response"] == "Test response"


async def test_chat_stream(client):
    resp = await client.post(
        "/api/chat/stream",
        json={"message": "hello", "session_id": "test-session"},
    )
    assert resp.status_code == 200


async def test_admin_reindex_requires_auth(client):
    with patch("app.api.router.settings") as mock_settings:
        mock_settings.app.admin_api_key = "secret"

        resp = await client.post("/api/admin/reindex")
        assert resp.status_code == 401


async def test_static_index(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Multicard" in resp.text
