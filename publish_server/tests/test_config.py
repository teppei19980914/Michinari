"""app/config.py のテスト。"""

from app.config import Settings, get_settings


def test_get_settings_returns_settings_instance():
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_database_url_accepts_postgresql_scheme():
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost/db")
    assert settings.database_url.startswith("postgresql+psycopg://")
