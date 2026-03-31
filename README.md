# Multicard Docs Assistant

[English](#english) | [Русский](#русский) | [O'zbek](#ozbek)

---

## English

Agentic RAG-powered documentation assistant for the Multicard payment platform API. Serves developers through a web chatbot, Telegram bot, and MCP server.

### Architecture

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

### Tech Stack

- **Framework**: FastAPI (async)
- **AI/RAG**: LlamaIndex FunctionAgent + VectorStoreIndex
- **LLM**: OpenAI (gpt-4o-mini default, configurable)
- **Embeddings**: text-embedding-3-small (1536 dim)
- **Database**: PostgreSQL with pgvector
- **MCP**: FastMCP (embedded HTTP + standalone stdio)
- **Telegram**: Polling (dev) / Webhook (prod)
- **Config**: python-decouple (.env)
- **Package Manager**: uv

### Prerequisites

- Python 3.12+
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key
- Telegram bot token (from [@BotFather](https://t.me/BotFather))

### Quick Start

```bash
git clone <repo-url> && cd multidocs
cp .env.example .env   # edit with your credentials
make setup             # install deps, create db, index docs
make run               # start the server
```

Open **[http://localhost:8000](http://localhost:8000)** for the web chatbot.

### Makefile Commands

```bash
make help          # show all commands
make run           # start the server
make run/debug     # start with hot reload
make index         # index docs into vector store
make mcp           # run standalone MCP server (stdio)
make db/create     # create database + pgvector
make db/psql       # open psql session
make lint          # run ruff linter
make format        # format code
make typecheck     # run mypy
make test          # run tests
make audit         # run all quality checks
make setup         # full project setup
```

### Project Structure

```text
.
├── main.py                        # FastAPI app, lifespan, middleware, MCP mount
├── Makefile                       # Dev/prod commands
├── .env.example                   # Environment template
├── docs/                          # Source documentation files
│   ├── docs.json                  # OpenAPI specification
│   └── docs.md                    # Markdown documentation
├── static/
│   └── index.html                 # Web chat UI
├── scripts/
│   ├── index.py                   # Document indexing CLI
│   └── mcp_server.py              # Standalone MCP server (stdio)
├── tests/                         # Test suite
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

### API Endpoints

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

### MCP Server

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

### Telegram Bot

Set `TELEGRAM_MODE` in `.env`:

- **`polling`** (default) — Bot pulls updates. Works locally, no public URL needed.
- **`webhook`** — Telegram pushes updates. Requires `TELEGRAM_WEBHOOK_URL` (public HTTPS) and `TELEGRAM_WEBHOOK_SECRET`.

The bot responds to all messages in private chats. In groups, it only responds when `@mentioned`.

### Adding Documentation

1. Place files in the `docs/` directory:
   - `.json` files are parsed as OpenAPI specs (one vector per endpoint)
   - `.md` files are chunked as general documentation

2. Run indexing:

   ```bash
   make index
   ```

Indexing uses SHA-256 checksums — unchanged files are skipped automatically.

### Memory System

Per-session two-tier memory (keyed by session ID):

- **Short-term**: FIFO chat history bounded by `MEMORY_TOKEN_LIMIT * 0.7`
- **Long-term**: FactExtractionMemoryBlock (auto-summarizes key facts) + VectorMemoryBlock (semantic recall of past conversations)

Session IDs: `tg_{chat_id}` for Telegram, client-provided UUID for web/API, `mcp_default` for MCP.

### Configuration

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

### Production Deployment

Key changes for production:

1. Set `TELEGRAM_MODE=webhook` with a public HTTPS URL
2. Set strong random values for `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`
3. Set `ALLOWED_ORIGINS` to your frontend domain(s)
4. Set `APP_DEBUG=False`
5. Use a managed PostgreSQL with pgvector support
6. Run behind a reverse proxy (nginx/caddy) with HTTPS

---

## Русский

RAG-ассистент для документации платёжной платформы Multicard API. Работает через веб-чатбот, Telegram-бот и MCP-сервер.

### Требования

- Python 3.12+
- PostgreSQL с расширением [pgvector](https://github.com/pgvector/pgvector)
- Пакетный менеджер [uv](https://docs.astral.sh/uv/)
- API-ключ OpenAI
- Токен Telegram-бота (от [@BotFather](https://t.me/BotFather))

### Быстрый старт

```bash
git clone <repo-url> && cd multidocs
cp .env.example .env   # заполните своими ключами
make setup             # установка зависимостей, создание БД, индексация
make run               # запуск сервера
```

Откройте **[http://localhost:8000](http://localhost:8000)** для веб-чатбота.

### Основные команды

```bash
make help          # показать все команды
make run           # запустить сервер
make run/debug     # запустить с hot reload
make index         # индексировать документацию
make mcp           # запустить MCP-сервер (stdio)
make db/create     # создать базу данных + pgvector
make lint          # запустить линтер
make test          # запустить тесты
make audit         # все проверки качества кода
```

### API-эндпоинты

| Метод | Путь | Авторизация | Описание |
| ----- | ---- | ----------- | -------- |
| GET | `/` | - | Веб-чатбот |
| GET | `/api/health` | - | Проверка состояния (БД + OpenAI) |
| POST | `/api/chat` | - | Чат (JSON запрос/ответ) |
| POST | `/api/chat/stream` | - | Чат (потоковый текстовый ответ) |
| POST | `/api/admin/reindex` | Admin | Переиндексация документации |
| POST | `/webhook/telegram` | Webhook secret | Вебхук Telegram |
| * | `/mcp/*` | Bearer токен | MCP-сервер (Streamable HTTP) |

### Telegram-бот

Установите `TELEGRAM_MODE` в `.env`:

- **`polling`** (по умолчанию) — бот сам запрашивает обновления. Работает локально без публичного URL.
- **`webhook`** — Telegram отправляет обновления. Требуется `TELEGRAM_WEBHOOK_URL` (публичный HTTPS) и `TELEGRAM_WEBHOOK_SECRET`.

Бот отвечает на все сообщения в личных чатах. В группах — только при `@упоминании`.

### Добавление документации

1. Поместите файлы в директорию `docs/`:
   - `.json` — парсятся как OpenAPI-спецификации (один вектор на эндпоинт)
   - `.md` — разбиваются на чанки как документация

2. Запустите индексацию:

   ```bash
   make index
   ```

Индексация использует SHA-256 контрольные суммы — неизменённые файлы пропускаются.

### MCP-сервер

**Встроенный** (работает с FastAPI на `/mcp`):

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

**Автономный** (stdio, для Claude Desktop / IDE):

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

### Продакшн

1. Установите `TELEGRAM_MODE=webhook` с публичным HTTPS URL
2. Задайте надёжные ключи для `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`
3. Укажите `ALLOWED_ORIGINS` с доменом(ами) вашего фронтенда
4. Установите `APP_DEBUG=False`
5. Используйте управляемый PostgreSQL с поддержкой pgvector
6. Запустите за обратным прокси (nginx/caddy) с HTTPS

---

## O'zbek

Multicard to'lov platformasi API dokumentatsiyasi uchun RAG-assistenti. Veb-chatbot, Telegram-bot va MCP-server orqali ishlatiladi.

### Talablar

- Python 3.12+
- [pgvector](https://github.com/pgvector/pgvector) kengaytmasi bilan PostgreSQL
- [uv](https://docs.astral.sh/uv/) paket menejeri
- OpenAI API kaliti
- Telegram bot tokeni ([@BotFather](https://t.me/BotFather) dan oling)

### Tez boshlash

```bash
git clone <repo-url> && cd multidocs
cp .env.example .env   # o'z kalitlaringizni kiriting
make setup             # bog'liqliklarni o'rnatish, bazani yaratish, indekslash
make run               # serverni ishga tushirish
```

Veb-chatbot uchun **[http://localhost:8000](http://localhost:8000)** sahifasini oching.

### Asosiy buyruqlar

```bash
make help          # barcha buyruqlarni ko'rsatish
make run           # serverni ishga tushirish
make run/debug     # hot reload bilan ishga tushirish
make index         # dokumentatsiyani indekslash
make mcp           # MCP-serverni ishga tushirish (stdio)
make db/create     # ma'lumotlar bazasini yaratish + pgvector
make lint          # linterni ishga tushirish
make test          # testlarni ishga tushirish
make audit         # kod sifatining barcha tekshiruvlari
```

### API endpointlari

| Metod | Yo'l | Autentifikatsiya | Tavsif |
| ----- | ---- | ---------------- | ------ |
| GET | `/` | - | Veb-chatbot |
| GET | `/api/health` | - | Holat tekshiruvi (DB + OpenAI) |
| POST | `/api/chat` | - | Chat (JSON so'rov/javob) |
| POST | `/api/chat/stream` | - | Chat (oqimli matnli javob) |
| POST | `/api/admin/reindex` | Admin | Dokumentatsiyani qayta indekslash |
| POST | `/webhook/telegram` | Webhook secret | Telegram webhook qabul qiluvchi |
| * | `/mcp/*` | Bearer token | MCP-server (Streamable HTTP) |

### Telegram bot

`.env` faylida `TELEGRAM_MODE` ni sozlang:

- **`polling`** (standart) — bot yangilanishlarni o'zi so'raydi. Lokal ishlaydi, umumiy URL talab qilinmaydi.
- **`webhook`** — Telegram yangilanishlarni jo'natadi. `TELEGRAM_WEBHOOK_URL` (umumiy HTTPS) va `TELEGRAM_WEBHOOK_SECRET` kerak.

Bot shaxsiy chatlarda barcha xabarlarga javob beradi. Guruhlarda faqat `@eslatilganda` javob beradi.

### Dokumentatsiya qo'shish

1. Fayllarni `docs/` papkasiga joylashtiring:
   - `.json` — OpenAPI spetsifikatsiyasi sifatida qayta ishlanadi (har bir endpoint uchun bitta vektor)
   - `.md` — dokumentatsiya sifatida bo'laklarga bo'linadi

2. Indekslashni ishga tushiring:

   ```bash
   make index
   ```

Indekslash SHA-256 nazorat yig'indisini ishlatadi — o'zgarmagan fayllar o'tkazib yuboriladi.

### MCP-server

**O'rnatilgan** (FastAPI bilan `/mcp` da ishlaydi):

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

**Mustaqil** (stdio, Claude Desktop / IDE uchun):

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

### Prodakshnga chiqarish

1. `TELEGRAM_MODE=webhook` ni umumiy HTTPS URL bilan sozlang
2. `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET` uchun kuchli tasodifiy kalitlar o'rnating
3. `ALLOWED_ORIGINS` ga frontend domeningizni kiriting
4. `APP_DEBUG=False` o'rnating
5. pgvector qo'llab-quvvatlaydigan boshqariladigan PostgreSQL ishlating
6. HTTPS bilan teskari proksi (nginx/caddy) orqasida ishga tushiring
