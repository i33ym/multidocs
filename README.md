# Multicard Docs Assistant

[English](#english) | [Русский](#русский) | [O'zbek](#ozbek)

---

## English

Agentic RAG-powered documentation assistant for the Multicard payment platform API. Serves developers through a web chatbot (with voice input), Telegram bot (text + voice messages), MCP server, and an MCP server generator for any OpenAPI spec.

### Architecture

```text
                    ┌──────────────┐
                    │   Web Chat   │  localhost:8000
                    │ (text+voice) │
                    └──────┬───────┘
                           │
┌──────────────┐   ┌──────┴───────┐   ┌──────────────┐
│   Telegram   ├───┤   FastAPI    ├───┤  MCP Server   │
│ (text+voice) │   │              │   │  (/mcp or     │
│  poll/webhook│   │  /api/chat   │   │   stdio)      │
└──────────────┘   │  /api/stream │   └──────────────┘
                   │  /api/specs  │
                   └──────┬───────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
    ┌──────┴──────┐ ┌─────┴─────┐ ┌──────┴──────┐
    │   Whisper   │ │ LlamaIndex│ │ MCP Server  │
    │   (audio    │ │   Agent   │ │  Generator  │
    │ transcribe) │ │(multi-step│ │  (codegen)  │
    └─────────────┘ │  ReAct)   │ └─────────────┘
                    ├───────────┤
                    │ 6 Tools:  │
                    │ search_*  │
                    │ get_*     │
                    │ list_*    │
                    │ by_tag    │
                    └─────┬─────┘
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
- **AI/RAG**: LlamaIndex FunctionAgent (multi-step ReAct) + VectorStoreIndex
- **LLM**: OpenAI (gpt-4o-mini default, configurable)
- **Speech-to-Text**: OpenAI Whisper (whisper-1)
- **Embeddings**: text-embedding-3-small (1536 dim)
- **Database**: PostgreSQL with pgvector
- **MCP**: FastMCP (embedded HTTP + standalone stdio)
- **Telegram**: Polling (dev) / Webhook (prod), text + voice messages
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
├── static/
│   └── index.html                 # Web chat UI (text + voice)
├── generated/                     # Auto-generated MCP servers (gitignored)
├── scripts/
│   ├── index.py                   # Document indexing CLI
│   └── mcp_server.py              # Standalone MCP server (stdio)
├── tests/                         # Test suite (47 tests)
└── app/
    ├── config.py                  # Settings via python-decouple
    ├── database.py                # Async engine, session factory
    ├── models.py                  # SQLAlchemy models
    ├── agent/
    │   ├── engine.py              # LLM, embeddings, vector store, memory, agent factories
    │   ├── tools.py               # 6 RAG tools (search, get, list, by_tag)
    │   └── prompts.py             # ReAct system prompt, context templates
    ├── generator/
    │   └── codegen.py             # OpenAPI → standalone MCP server generator
    ├── indexing/
    │   ├── parser.py              # OpenAPI spec → Documents with metadata
    │   ├── loader.py              # Multi-format loader (md, json, yaml, pdf, docx, html, csv, txt)
    │   └── pipeline.py            # Indexing with checksum tracking
    ├── api/
    │   ├── router.py              # All API endpoints
    │   ├── schemas.py             # Pydantic request/response models
    │   └── deps.py                # AppState singleton
    ├── telegram/
    │   ├── webhook.py             # Polling + webhook modes, text + voice handling
    │   ├── handlers.py            # Message storage, ring buffer, context
    │   ├── audio.py               # Whisper voice transcription
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
| POST | `/api/transcribe` | - | Audio → text via Whisper |
| POST | `/api/admin/reindex` | Admin | Force re-index all documents |
| POST | `/api/admin/specs` | Admin | Upload OpenAPI spec → generate MCP server |
| GET | `/api/admin/specs` | Admin | List generated MCP servers |
| DELETE | `/api/admin/specs/{name}` | Admin | Delete a generated MCP server |
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

# Voice transcription
curl -X POST http://localhost:8000/api/transcribe \
  -F "file=@recording.webm"
```

### Agentic RAG

The agent uses a multi-step ReAct approach with 6 tools:

| Tool | Purpose |
| ---- | ------- |
| `search_docs` | Broad semantic search across all indexed content |
| `search_endpoints` | Filtered search over API endpoint definitions |
| `search_guides` | Filtered search over markdown guides |
| `get_endpoint_details` | Full JSON spec for a specific endpoint (path + method) |
| `list_endpoints` | List all endpoints, optionally filter by tag |
| `search_by_tag` | Find all endpoints in a category (fuzzy tag matching) |

The agent chains multiple tool calls per query: discover endpoints → fetch details → cross-reference guides → synthesize a complete answer with code examples.

### Voice Input

Voice messages are transcribed using OpenAI Whisper (`whisper-1`):

- **Web chatbot**: Click the mic button to record, click again to stop. Audio is transcribed and sent automatically.
- **Telegram**: Send a voice message or audio file. The bot transcribes it and responds to the text.

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

### MCP Server Generator

Upload any OpenAPI spec and get a standalone MCP server generated automatically:

```bash
# Upload spec
curl -X POST http://localhost:8000/api/admin/specs \
  -H "Authorization: Bearer your-admin-key" \
  -H "Content-Type: application/json" \
  -d @my-api-spec.json

# List generated servers
curl http://localhost:8000/api/admin/specs \
  -H "Authorization: Bearer your-admin-key"

# Delete a server
curl -X DELETE http://localhost:8000/api/admin/specs/my_api \
  -H "Authorization: Bearer your-admin-key"
```

Each generated server includes:

- `server.py` — standalone FastMCP server with one tool per endpoint
- `spec.json` — original spec
- `mcp_config.json` — ready-to-paste config for Claude Desktop / IDE
- `README.md` — auto-generated documentation

Developers copy the `mcp_config.json` into their MCP client and Claude/Cursor instantly has structured knowledge of that API for generating accurate client code.

### Adding Documentation

1. Drop files into the `docs/` directory. Supported formats:

   | Format | Extensions |
   | ------ | ---------- |
   | Markdown | `.md` |
   | Plain text | `.txt`, `.rst` |
   | OpenAPI | `.json`, `.yaml`, `.yml` |
   | PDF | `.pdf` |
   | Word | `.docx` |
   | HTML | `.html`, `.htm` |
   | CSV | `.csv` |

2. Run indexing:

   ```bash
   make index
   ```

Indexing uses SHA-256 checksums — unchanged files are skipped. Custom formats can be added with the `@register_loader` decorator in [loader.py](app/indexing/loader.py).

### Telegram Bot

Set `TELEGRAM_MODE` in `.env`:

- **`polling`** (default) — Bot pulls updates. Works locally, no public URL needed.
- **`webhook`** — Telegram pushes updates. Requires `TELEGRAM_WEBHOOK_URL` (public HTTPS) and `TELEGRAM_WEBHOOK_SECRET`.

The bot responds to all messages in private chats. In groups, it only responds when `@mentioned`. Supports both text and voice messages.

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

1. Set `TELEGRAM_MODE=webhook` with a public HTTPS URL
2. Set strong random values for `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`
3. Set `ALLOWED_ORIGINS` to your frontend domain(s)
4. Set `APP_DEBUG=False`
5. Use a managed PostgreSQL with pgvector support
6. Run behind a reverse proxy (nginx/caddy) with HTTPS

---

## Русский

Агентный RAG-ассистент для документации платёжной платформы Multicard API. Работает через веб-чатбот (с голосовым вводом), Telegram-бот (текст + голосовые сообщения), MCP-сервер и генератор MCP-серверов из любой OpenAPI-спецификации.

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
| POST | `/api/transcribe` | - | Аудио → текст через Whisper |
| POST | `/api/admin/reindex` | Admin | Переиндексация документации |
| POST | `/api/admin/specs` | Admin | Загрузка OpenAPI → генерация MCP-сервера |
| GET | `/api/admin/specs` | Admin | Список сгенерированных MCP-серверов |
| DELETE | `/api/admin/specs/{name}` | Admin | Удаление сгенерированного MCP-сервера |
| POST | `/webhook/telegram` | Webhook secret | Вебхук Telegram |
| * | `/mcp/*` | Bearer токен | MCP-сервер (Streamable HTTP) |

### Агентный RAG

Агент использует многошаговый ReAct-подход с 6 инструментами:

| Инструмент | Назначение |
| ---------- | ---------- |
| `search_docs` | Семантический поиск по всей индексированной документации |
| `search_endpoints` | Поиск по определениям API-эндпоинтов |
| `search_guides` | Поиск по markdown-руководствам |
| `get_endpoint_details` | Полная JSON-спецификация конкретного эндпоинта |
| `list_endpoints` | Список всех эндпоинтов с фильтрацией по тегу |
| `search_by_tag` | Поиск всех эндпоинтов в категории (нечёткое совпадение) |

Агент цепочкой вызывает несколько инструментов: находит эндпоинты → получает детали → сверяет с руководствами → формирует полный ответ с примерами кода.

### Голосовой ввод

Голосовые сообщения транскрибируются через OpenAI Whisper (`whisper-1`):

- **Веб-чатбот**: нажмите кнопку микрофона для записи, нажмите снова для остановки
- **Telegram**: отправьте голосовое сообщение или аудиофайл

### Генератор MCP-серверов

Загрузите любую OpenAPI-спецификацию и получите готовый MCP-сервер:

```bash
curl -X POST http://localhost:8000/api/admin/specs \
  -H "Authorization: Bearer your-admin-key" \
  -H "Content-Type: application/json" \
  -d @my-api-spec.json
```

Генерируется: `server.py`, `spec.json`, `mcp_config.json`, `README.md`. Разработчик копирует `mcp_config.json` в свой MCP-клиент — и Claude/Cursor мгновенно получает структурированные знания об этом API.

### Добавление документации

Поддерживаемые форматы: `.md`, `.txt`, `.rst`, `.json`, `.yaml`, `.yml`, `.pdf`, `.docx`, `.html`, `.htm`, `.csv`

1. Поместите файлы в директорию `docs/`
2. Запустите `make index`

Пользовательские форматы добавляются через декоратор `@register_loader` в [loader.py](app/indexing/loader.py).

### Telegram-бот

Установите `TELEGRAM_MODE` в `.env`:

- **`polling`** (по умолчанию) — работает локально без публичного URL
- **`webhook`** — для продакшна, требуется публичный HTTPS URL

Бот отвечает на все сообщения в личных чатах. В группах — только при `@упоминании`. Поддерживает текст и голосовые сообщения.

### Продакшн

1. Установите `TELEGRAM_MODE=webhook` с публичным HTTPS URL
2. Задайте надёжные ключи для `MCP_API_KEY`, `ADMIN_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`
3. Укажите `ALLOWED_ORIGINS` с доменом(ами) вашего фронтенда
4. Установите `APP_DEBUG=False`
5. Используйте управляемый PostgreSQL с поддержкой pgvector
6. Запустите за обратным прокси (nginx/caddy) с HTTPS

---

## O'zbek

Multicard to'lov platformasi API dokumentatsiyasi uchun agentli RAG-assistent. Veb-chatbot (ovozli kiritish bilan), Telegram-bot (matn + ovozli xabarlar), MCP-server va har qanday OpenAPI spetsifikatsiyasidan MCP-server generatori orqali ishlaydi.

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
| POST | `/api/transcribe` | - | Audio → matn Whisper orqali |
| POST | `/api/admin/reindex` | Admin | Dokumentatsiyani qayta indekslash |
| POST | `/api/admin/specs` | Admin | OpenAPI yuklash → MCP-server generatsiyasi |
| GET | `/api/admin/specs` | Admin | Generatsiya qilingan MCP-serverlar ro'yxati |
| DELETE | `/api/admin/specs/{name}` | Admin | Generatsiya qilingan MCP-serverni o'chirish |
| POST | `/webhook/telegram` | Webhook secret | Telegram webhook qabul qiluvchi |
| * | `/mcp/*` | Bearer token | MCP-server (Streamable HTTP) |

### Agentli RAG

Agent ko'p bosqichli ReAct yondashuvi bilan 6 ta asbobdan foydalanadi:

| Asbob | Maqsad |
| ----- | ------ |
| `search_docs` | Barcha indekslangan kontent bo'yicha semantik qidiruv |
| `search_endpoints` | API endpoint ta'riflari bo'yicha filtrlangan qidiruv |
| `search_guides` | Markdown qo'llanmalar bo'yicha filtrlangan qidiruv |
| `get_endpoint_details` | Muayyan endpoint uchun to'liq JSON spetsifikatsiya |
| `list_endpoints` | Barcha endpointlar ro'yxati, teg bo'yicha filtr |
| `search_by_tag` | Kategoriya bo'yicha barcha endpointlarni topish |

Agent bir so'rov uchun bir nechta asbobni zanjirlab chaqiradi: endpointlarni topadi → tafsilotlarni oladi → qo'llanmalar bilan solishtiradi → kod misollari bilan to'liq javob beradi.

### Ovozli kiritish

Ovozli xabarlar OpenAI Whisper (`whisper-1`) orqali transkripsiya qilinadi:

- **Veb-chatbot**: yozish uchun mikrofon tugmasini bosing, to'xtatish uchun yana bosing
- **Telegram**: ovozli xabar yoki audio fayl yuboring

### MCP-server generatori

Har qanday OpenAPI spetsifikatsiyasini yuklang va tayyor MCP-server oling:

```bash
curl -X POST http://localhost:8000/api/admin/specs \
  -H "Authorization: Bearer your-admin-key" \
  -H "Content-Type: application/json" \
  -d @my-api-spec.json
```

Generatsiya qilinadi: `server.py`, `spec.json`, `mcp_config.json`, `README.md`. Dasturchi `mcp_config.json` ni MCP-klientiga nusxalaydi — va Claude/Cursor shu zahoti ushbu API haqida tuzilgan bilimga ega bo'ladi.

### Dokumentatsiya qo'shish

Qo'llab-quvvatlanadigan formatlar: `.md`, `.txt`, `.rst`, `.json`, `.yaml`, `.yml`, `.pdf`, `.docx`, `.html`, `.htm`, `.csv`

1. Fayllarni `docs/` papkasiga joylashtiring
2. `make index` ni ishga tushiring

Maxsus formatlar [loader.py](app/indexing/loader.py) dagi `@register_loader` dekoratori orqali qo'shiladi.

### Telegram bot

`.env` faylida `TELEGRAM_MODE` ni sozlang:

- **`polling`** (standart) — lokal ishlaydi, umumiy URL talab qilinmaydi
- **`webhook`** — prodakshn uchun, umumiy HTTPS URL kerak

Bot shaxsiy chatlarda barcha xabarlarga javob beradi. Guruhlarda faqat `@eslatilganda` javob beradi. Matn va ovozli xabarlarni qo'llab-quvvatlaydi.

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
