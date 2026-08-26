"""アプリケーションのインフラ設定（DB接続先など）。

業務上の閾値・パラメータは app_setting テーブルへ外部化する対象であり、
ここには含めない（CLAUDE.md「アプリ固有規約」参照）。
"""

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _default_data_dir() -> Path:
    """データ保存先ディレクトリを解決する（配布パッケージ対応）。

    PyInstallerでパッケージ化された実行ファイル（`sys.frozen`）として起動している
    場合、インストール先フォルダは書き込み権限が保証されない（Program Files等）ため、
    利用者ごとに書き込み可能なディレクトリ（Windowsの `%LOCALAPPDATA%`）を使う。
    ソースから起動する開発環境ではこれまで通りリポジトリ直下の data/ を使う
    （既存の開発者データへの影響を避けるため、frozen判定時のみ挙動を切り替える）。
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / "Michinari" / "data"
    return REPO_ROOT / "data"


DEFAULT_DATA_DIR = _default_data_dir()
#: データ構造編8章のディレクトリ構成「data/ データベースファイル、バックアップ、エクスポート」。
BACKUP_DIR = DEFAULT_DATA_DIR / "backups"
EXPORT_DIR = DEFAULT_DATA_DIR / "exports"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MICHINARI_", env_file=".env")

    database_url: str = f"sqlite:///{(DEFAULT_DATA_DIR / 'michinari.db').as_posix()}"
    # 起動時に app_setting.server.port が取得できない場合の最終フォールバック値のみ。
    # 通常の起動ポートは app_setting テーブル（server.port）から取得する。
    fallback_server_port: int = 8100


def get_settings() -> Settings:
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
