"""Настройки сервера. Всё читается из переменных окружения с префиксом TASKER_."""

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Версия сервера и то, какие версии API он умеет отдавать.
# Клиент узнаёт это через /.well-known/tasker и подстраивается.
SERVER_VERSION = "2.0.0"
API_VERSIONS = ["v1"]
MIN_CLIENT_VERSION = "1.0.0"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TASKER_", extra="ignore")

    # sqlite:///... для запуска в один контейнер, postgresql+psycopg://... для полноценного
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    # Пустой секрет означает «сгенерируй и запомни» — иначе при каждом рестарте
    # у всех разлогинивало бы сессии.
    jwt_secret: str = ""
    jwt_ttl_hours: int = 24 * 14

    # Мобильный клиент и сторонний фронт ходят с другого источника
    cors_origins: str = "*"

    # Публичный инстанс можно закрыть от новых регистраций
    allow_registration: bool = True

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_jwt_secret(self) -> str:
        """Секрет из окружения, иначе — сохранённый на диске, иначе новый."""
        if self.jwt_secret:
            return self.jwt_secret
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        keyfile = DATA_DIR / ".jwt_secret"
        if not keyfile.exists():
            keyfile.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        return keyfile.read_text(encoding="utf-8").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
