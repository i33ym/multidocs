# Multicard Docs Assistant

Agentic RAG-powered documentation assistant for the Multicard payment platform API. Serves developers through a web chatbot, Telegram bot, and MCP server.

## Architecture

```text
                    ┌──────────────┐
                    │   Web Chat   │  localhost:8000
                    │   (HTML UI)  │
                    └──────┬───────┘
                           │
┌──────────────┐   ┌──────┴───────┐   ┌──────────────┐
│   Telegram   ├───┤   FastAPI    ├───┤  MCP Server   │
│  Bot (poll/  │   │              │   │  (/mcp or     │
│   webhook)   │   │  /api/chat   │   │   stdio)      │
└──────────────┘   │  /api/stream │   └──────────────┘
                   └──────┬───────┘
                          │
                ┌─────────┴──────────┐
                │  LlamaIndex Agent  │
                │  (FunctionAgent)   │
                ├────────────────────┤
                │  Tools:            │
                │  - search_docs     │
                │  - search_endpoints│
                │  - search_guides   │
                │  - get_endpoint    │
                │  - list_endpoints  │
                └─────────┬──────────┘
                          │
              ┌───────────┴───────────┐
              │  PostgreSQL + pgvector │
              │  - document_embeddings│
              │  - memory (per-session│
              │    facts + vectors)   │
              │  - telegram_messages  │
              │  - indexed_files      │
              └───────────────────────┘
```

## Tech Stack

- **Framework**: FastAPI (async)
- **AI/RAG**: LlamaIndex FunctionAgent + VectorStoreIndex
- **LLM**: OpenAI (gpt-4o-mini default, configurable)
- **Embeddings**: text-embedding-3-small (1536 dim)
- **Database**: PostgreSQL with pgvector
- **MCP**: FastMCP (embedded HTTP + standalone stdio)
- **Telegram**: Polling (dev) / Webhook (prod)
- **Config**: python-decouple (.env)
- **Package Manager**: uv

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key
- Telegram bot token (from [@BotFather](https://t.me/BotFather))

### Setup

```bash
# Clone and install
git clone <repo-url> && cd multidocs
uv sync

# Configure
cp .env.example .env
# Edit .env with your credentials

# Create the database
createdb multidocs
psql -d multidocs -c "CREATE EXTENSION vector"

# Index documentation
uv run python scripts/index.py

# Start the server
uv run python main.py
```

Open **[http://localhost:8000](http://localhost:8000)** for the web chatbot.

## Project Structure

```text
.
├── main.py                        # FastAPI app, lifespan, middleware, MCP mount
├── .env.example                   # Environment template
├── docs/                          # Source documentation files
│   ├── docs.json                  # OpenAPI specification
│   └── docs.md                    # Markdown documentation
├── static/
│   └── index.html                 # Web chat UI
├── scripts/
│   ├── index.py                   # Document indexing CLI
│   └── mcp_server.py              # Standalone MCP server (stdio)
└── app/
    ├── config.py                  # Settings via python-decouple
    ├── database.py                # Async engine, session factory
    ├── models.py                  # SQLAlchemy models
    ├── agent/
    │   ├── engine.py              # LLM, embeddings, vector store, memory, agent factories
    │   ├── tools.py               # RAG tools (search, get, list)
    │   └── prompts.py             # System prompt, context templates
    ├── indexing/
    │   ├── parser.py              # OpenAPI spec → Documents with metadata
    │   ├── loader.py              # Markdown + OpenAPI document loading
    │   └── pipeline.py            # Indexing with checksum tracking
    ├── api/
    │   ├── router.py              # /api/health, /api/chat, /api/chat/stream, /api/admin/reindex
    │   ├── schemas.py             # Pydantic request/response models
    │   └── deps.py                # AppState singleton
    ├── telegram/
    │   ├── webhook.py             # Polling + webhook modes, message handling
    │   ├── handlers.py            # Message storage, ring buffer, context
    │   └── formatter.py           # Markdown → Telegram HTML
    └── mcp/
        └── server.py              # FastMCP tools
```

## API Endpoints

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/` | - | Web chat UI |
| GET | `/api/health` | - | Health check (DB + OpenAI status) |
| POST | `/api/chat` | - | Chat (JSON request/response) |
| POST | `/api/chat/stream` | - | Chat (streaming text response) |
| POST | `/api/admin/reindex` | Admin | Force re-index all documents |
| POST | `/webhook/telegram` | Webhook secret | Telegram webhook receiver |
| * | `/mcp/*` | Bearer token | MCP server (Streamable HTTP) |

### Chat API

```bash
# Standard
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I authenticate?", "session_id": "my-session"}'

# Streaming
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I authenticate?", "session_id": "my-session"}'

# Reindex (requires ADMIN_API_KEY)
curl -X POST http://localhost:8000/api/admin/reindex \
  -H "Authorization: Bearer your-admin-api-key"
```

## MCP Server

Two modes:

**Embedded** (runs with FastAPI at `/mcp`):
```json
{
  "mcpServers": {
    "multicard": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp",
      "headers": { "Authorization": "Bearer your-mcp-api-key" }
    }
  }
}
```

**Standalone** (stdio, for Claude Desktop / IDE):
```json
{
  "mcpServers": {
    "multicard": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "/path/to/multidocs"
    }
  }
}
```

**Available tools**: `search_docs`, `search_endpoints`, `get_endpoint`, `list_api_endpoints`, `ask_multicard`

## Telegram Bot

Set `TELEGRAM_MODE` in `.env`:

- **`polling`** (default) — Bot pulls updates. Works locally, no public URL needed.
- **`webhook`** — Telegram pushes updates. Requires `TELEGRAM_WEBHOOK_URL` (public HTTPS) and `TELEGRAM_WEBHOOK_SECRET`.

The bot responds to all messages in private chats. In groups, it only responds when `@mentioned`.

## Adding Documentation

1. Place files in the `docs/` directory:
   - `.json` files are parsed as OpenAPI specs (one vector per endpoint)
   - `.md` files are chunked as general documentation
2. Run indexing:

   ```bash
   uv run python scripts/index.py
   ```

   Or hit the admin endpoint:

   ```bash
   curl -X POST http://localhost:8000/api/admin/reindex \
     -H "Authorization: Bearer your-admin-api-key"
   ```

Indexing uses SHA-256 checksums — unchanged files are skipped automatically.

## Memory System

Per-session two-tier memory (keyed by session ID):

- **Short-term**: FIFO chat history bounded by `MEMORY_TOKEN_LIMIT * 0.7`
- **Long-term**: FactExtractionMemoryBlock (auto-summarizes key facts) + VectorMemoryBlock (semantic recall of past conversations)

Session IDs: `tg_{chat_id}` for Telegram, client-provided UUID for web/API, `mcp_default` for MCP.

## Configuration

All settings via `.env` — see [.env.example](.env.example) for the full list. Key groups:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | gpt-4o-mini | LLM model |
| `DATABASE_*` | localhost:5432 | PostgreSQL connection |
| `TELEGRAM_MODE` | polling | `polling` or `webhook` |
| `MCP_API_KEY` | required | Bearer token for /mcp |
| `ADMIN_API_KEY` | empty | Bearer token for admin endpoints |
| `AGENT_TIMEOUT` | 120 | Max seconds per agent call |
| `RATE_LIMIT_RPM` | 30 | Requests per minute per session |
| `MEMORY_TOKEN_LIMIT` | 40000 | Memory context window |
| `MEMORY_MAX_FACTS` | 50 | Max extracted facts per session |

## Production Deployment

Key changes for production:

1. Set `TELEGRAM_MODE=webhook` with a public HTTPS URL
2. Set strong random values for `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`
3. Set `ALLOWED_ORIGINS` to your frontend domain(s)
4. Set `APP_DEBUG=False`
5. Use a managed PostgreSQL with pgvector support
6. Run behind a reverse proxy (nginx/caddy) with HTTPS
