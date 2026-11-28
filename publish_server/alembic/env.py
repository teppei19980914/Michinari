"""Alembicマイグレーション実行環境（backend/alembic/env.pyと同じ方針。別実装、D-24と同種）。

- sys.pathにpublish_server/を追加し、app パッケージを解決可能にする
- app.models.Base.metadataを取り込み、autogenerateがモデル定義と実DBスキーマの差分を
  検出できるようにする
- 接続先はapp.config.get_settings().database_urlを使い、二重管理しない
- render_as_batchはSQLite（テスト時のみ使用、D-23）でのみ有効にする。PostgreSQL
  （本番、Supabase）ではテーブル再作成を伴うbatch modeは不要かつ非効率なため使わない
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_database_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", _database_url)

target_metadata = Base.metadata
_use_batch_mode = _database_url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_use_batch_mode,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_use_batch_mode,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
