"""データ管理（バックアップ・全データのエクスポート/インポート、
設計書データ構造編6.2「設定・データ管理」、仕様書6.12 SC-12、実装フェーズ分割計画書Phase10）。

「全データのエクスポート／インポート」は、データ構造編7章のナレッジエクスポート専用JSON
スキーマとは別に、全テーブルを汎用的にJSON化する形式で実現する（実装フェーズ分割計画書
Phase10完了条件「JSON出力をインポートして復元できる」）。テーブル定義（`Base.metadata`）
から動的に全テーブル・全行を読み書きするため、テーブル追加時にもこのモジュールの改修は
不要（CLAUDE.md DRYの原則）。

一方、バックアップ（`create_backup`/`restore_backup`）は仕様書6.12「データベースファイルの
複製を作成」の通り、SQLiteファイルそのものを複製する方式のまま据え置く（エクスポート/
インポートとは別の完了条件・別の操作であり、混同しない）。
"""

import datetime as dt
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BACKUP_DIR, get_settings
from app.constants.app_setting_keys import BACKUP_RETENTION_COUNT
from app.database import engine
from app.models.base import Base
from app.services import setting_reader
from app.services.exceptions import NotFoundError, ValidationError

#: バックアップファイル名の形式（作成日時の古い順ソート・IDとの往復に使う）。
_BACKUP_NAME_PATTERN = re.compile(r"^backup_(\d{8}_\d{6})\.db$")

#: 全データエクスポートJSONのスキーマ版数（データ構造編9章D-04と同じ方針：固定文字列とし、
#: インポート時に不一致なら拒否する。ナレッジエクスポート（export_service.SCHEMA_VERSION）
#: とは別用途のため別定数とする）。
DATA_SCHEMA_VERSION = "1.0"


def _database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise ValidationError("バックアップ機構はSQLite以外のデータベースには対応していません")
    return Path(url.removeprefix("sqlite:///"))


@dataclass(frozen=True)
class BackupInfo:
    id: str
    created_at: dt.datetime
    size_bytes: int


def _backup_path(backup_id: str) -> Path:
    match = _BACKUP_NAME_PATTERN.fullmatch(f"{backup_id}.db")
    if match is None:
        raise NotFoundError("バックアップ", backup_id)
    return BACKUP_DIR / f"{backup_id}.db"


def list_backups() -> list[BackupInfo]:
    """作成日時の新しい順に一覧を返す（データ構造編6.2 GET /data/backups）。"""
    if not BACKUP_DIR.exists():
        return []
    infos = []
    for path in BACKUP_DIR.glob("backup_*.db"):
        match = _BACKUP_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        created_at = dt.datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(
            tzinfo=dt.UTC
        )
        infos.append(
            BackupInfo(id=path.stem, created_at=created_at, size_bytes=path.stat().st_size)
        )
    infos.sort(key=lambda info: info.created_at, reverse=True)
    return infos


def _prune_old_backups(retention_count: int) -> None:
    """retention_countを超える古いバックアップを削除する（データ構造編6.2「D-02」、既定5）。"""
    infos = list_backups()
    for info in infos[retention_count:]:
        _backup_path(info.id).unlink(missing_ok=True)


def create_backup(session: Session) -> BackupInfo:
    """データベースファイルの複製を作成する（仕様書6.12「バックアップ」）。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    backup_id = f"backup_{timestamp}"
    destination = BACKUP_DIR / f"{backup_id}.db"

    engine.dispose()  # SQLiteファイルのコピー前に接続を解放する（Windowsのファイルロック対策）
    shutil.copy2(_database_path(), destination)

    retention_count = setting_reader.get_int(session, BACKUP_RETENTION_COUNT)
    _prune_old_backups(retention_count)

    return BackupInfo(
        id=backup_id, created_at=dt.datetime.now(dt.UTC), size_bytes=destination.stat().st_size
    )


def _create_safety_copy(db_path: Path, suffix: str) -> None:
    """復元・インポートで現在のDBを差し替える直前に、安全退避コピーを作成する
    （誤操作からの回復手段を残すため。restore_backup・import_all_dataで共用、
    CLAUDE.md DRYの原則）。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    shutil.copy2(db_path, BACKUP_DIR / f"backup_{timestamp}_{suffix}.db")


def restore_backup(backup_id: str) -> None:
    """バックアップから復元する（仕様書6.12「バックアップ一覧」の復元操作）。

    復元前に現在のDBの安全退避コピーを作成する（誤操作からの回復手段を残すため）。
    """
    source = _backup_path(backup_id)
    if not source.exists():
        raise NotFoundError("バックアップ", backup_id)

    engine.dispose()
    db_path = _database_path()
    _create_safety_copy(db_path, "pre_restore")

    shutil.copy2(source, db_path)


def _ordered_table_names() -> list[str]:
    """外部キー依存順（親→子）のテーブル名一覧を返す。INSERTはこの順、
    DELETEは逆順が安全（`Base.metadata.sorted_tables`はFK依存を解決した順序を返す）。
    Alembic自身が管理する`alembic_version`テーブルはBase.metadataに含まれないため、
    エクスポート/インポートの対象から自然に除外される（スキーマ移行状態には触れない）。
    """
    return [table.name for table in Base.metadata.sorted_tables]


def export_all_data() -> dict:
    """全データのエクスポート（仕様書6.12「エクスポート」、データ構造編6.2 GET /data/export）。

    SQLiteファイルを直接読み取り、テーブルごとの行をそのままJSON化する
    （SQLAlchemyの型変換を経由しないため、日付・真偽値等もSQLite上の生の格納表現
    のまま往復し、インポート時の型解釈の齟齬を避けられる）。
    """
    db_path = _database_path()
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            table_name: [
                dict(row) for row in connection.execute(f"SELECT * FROM {table_name}").fetchall()
            ]
            for table_name in _ordered_table_names()
        }
    finally:
        connection.close()

    return {
        "schema_version": DATA_SCHEMA_VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "tables": tables,
    }


def _validate_full_data_export(data: dict) -> None:
    """アップロードされたJSONが本アプリの全データエクスポート形式として妥当かを検証する
    （データ構造編9章D-04と同じ考え方：想定外の形式・版数を静かに受け入れない）。"""
    if not isinstance(data, dict) or "tables" not in data:
        raise ValidationError("インポートファイルが有効なエクスポート形式ではありません")
    if data.get("schema_version") != DATA_SCHEMA_VERSION:
        raise ValidationError(
            f"インポートファイルのスキーマ版数が対応していません"
            f"（対応: {DATA_SCHEMA_VERSION}、受領: {data.get('schema_version')}）"
        )
    required_tables = {"goal", "material", "app_setting"}
    if not required_tables.issubset(data["tables"].keys()):
        raise ValidationError("インポートファイルはミチナリのデータベースではありません")


def import_all_data(data: dict) -> None:
    """データのインポート（仕様書6.12「既存データの上書きを確認」。確認自体はフロントエンドの
    確認モーダルで行い、本関数は確認済みの実行のみを担う）。

    復元と同じく、実行前に現在のDBの安全退避コピーを作成する。全テーブルを削除してから
    エクスポートJSONの内容で再構築する（外部キー依存順を守った削除・挿入順序で行う）。
    """
    _validate_full_data_export(data)

    engine.dispose()
    db_path = _database_path()
    _create_safety_copy(db_path, "pre_import")

    table_names = _ordered_table_names()
    connection = sqlite3.connect(db_path)
    try:
        for table_name in reversed(table_names):
            connection.execute(f"DELETE FROM {table_name}")
        for table_name in table_names:
            rows = data["tables"].get(table_name) or []
            if not rows:
                continue
            columns = list(rows[0].keys())
            column_list = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})",
                [tuple(row[column] for column in columns) for row in rows],
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
