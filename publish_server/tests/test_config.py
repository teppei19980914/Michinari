"""app/config.py のテスト。"""

from app.config import Settings, get_settings


def test_get_settings_returns_settings_instance():
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_is_production_like_false_for_sqlite_default():
    settings = Settings(database_url="sqlite:///./x.db")
    assert settings.is_production_like() is False


def test_is_production_like_true_for_postgresql():
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost/db")
    assert settings.is_production_like() is True
