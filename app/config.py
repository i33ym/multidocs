from dataclasses import dataclass

from decouple import config


@dataclass(frozen=True, slots=True)
class OpenAIConfig:
    api_key: str = config("OPENAI_API_KEY")
    model: str = config("OPENAI_MODEL", default="gpt-4o-mini")
    embedding_model: str = config(
        "OPENAI_EMBEDDING_MODEL", default="text-embedding-3-small"
    )


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str = config("DATABASE_HOST", default="localhost")
    port: int = config("DATABASE_PORT", default=5432, cast=int)
    name: str = config("DATABASE_NAME", default="multidocs")
    user: str = config("DATABASE_USER", default="multidocs")
    password: str = config("DATABASE_PASSWORD")

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str = config("TELEGRAM_BOT_TOKEN")
    bot_username: str = config("TELEGRAM_BOT_USERNAME")
    mode: str = config("TELEGRAM_MODE", default="polling")
    webhook_secret: str = config("TELEGRAM_WEBHOOK_SECRET", default="")
    webhook_url: str = config("TELEGRAM_WEBHOOK_URL", default="")


@dataclass(frozen=True, slots=True)
class MCPConfig:
    api_key: str = config("MCP_API_KEY")


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    chat_history_limit: int = config("CHAT_HISTORY_LIMIT", default=100, cast=int)
    token_limit: int = config("MEMORY_TOKEN_LIMIT", default=40000, cast=int)
    max_facts: int = config("MEMORY_MAX_FACTS", default=50, cast=int)


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str = config("APP_HOST", default="0.0.0.0")
    port: int = config("APP_PORT", default=8000, cast=int)
    debug: bool = config("APP_DEBUG", default=False, cast=bool)
    docs_dir: str = config("DOCS_DIR", default="docs")
    admin_api_key: str = config("ADMIN_API_KEY", default="")
    allowed_origins: str = config("ALLOWED_ORIGINS", default="*")
    agent_timeout: int = config("AGENT_TIMEOUT", default=120, cast=int)
    rate_limit_rpm: int = config("RATE_LIMIT_RPM", default=30, cast=int)


@dataclass(frozen=True, slots=True)
class Settings:
    openai: OpenAIConfig = OpenAIConfig()
    database: DatabaseConfig = DatabaseConfig()
    telegram: TelegramConfig = TelegramConfig()
    mcp: MCPConfig = MCPConfig()
    memory: MemoryConfig = MemoryConfig()
    app: AppConfig = AppConfig()


settings = Settings()
