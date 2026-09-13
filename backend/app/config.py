"""アプリケーションのインフラ設定（DB接続先など）。

業務上の閾値・パラメータは app_setting テーブルへ外部化する対象であり、
ここには含めない（CLAUDE.md「アプリ固有規約」参照）。
"""

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import desktop as desktop_constants

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


def resolve_bundled_path(bundled_relative: str, source_path: Path) -> Path:
    """配布パッケージへ同梱したファイルの配置先を解決する。

    PyInstallerでパッケージ化された実行ファイル（`sys.frozen`）として起動している場合、
    同梱物は展開先（`sys._MEIPASS`）の下に置かれる。ソースから起動する開発環境では
    リポジトリ内の原本を使う。フロントエンドの静的ファイル・`alembic.ini`・ロケール・
    アイコンの4箇所が同じ判定を必要とするため、ここへ集約する（CLAUDE.md DRYの原則）。

    引数:
        bundled_relative: 配布パッケージ内での相対パス（`build_package.build_backend`の
            `--add-data`の指定先と一致させること）。
        source_path: 開発環境で使うリポジトリ内の絶対パス。

    返り値:
        解決したパス（存在するとは限らない。存在確認は呼び出し側が行う）。

    使用例:
        >>> resolve_bundled_path("alembic.ini", BACKEND_DIR / "alembic.ini")  # doctest: +SKIP
        WindowsPath('.../backend/alembic.ini')
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / bundled_relative
    return source_path


DEFAULT_DATA_DIR = _default_data_dir()
#: データ構造編8章のディレクトリ構成「data/ データベースファイル、バックアップ、エクスポート」。
BACKUP_DIR = DEFAULT_DATA_DIR / "backups"
EXPORT_DIR = DEFAULT_DATA_DIR / "exports"
#: 常駐時のログ出力先（Phase37）。コンソールを表示しなくなったため、起動失敗や通知の記録は
#: ここだけに残る。BACKUP_DIR・EXPORT_DIR と同じくデータフォルダ配下へ置く
#: （配布時は `%LOCALAPPDATA%\\Michinari\\data\\logs\\`。開発環境では `data/logs/` となり、
#: `.gitignore` の `data/*` で既に除外されているため新たな除外指定を要しない）。
LOG_DIR = DEFAULT_DATA_DIR / desktop_constants.LOG_DIR_NAME


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MICHINARI_", env_file=".env")

    database_url: str = f"sqlite:///{(DEFAULT_DATA_DIR / 'michinari.db').as_posix()}"
    # 起動時に app_setting.server.port が取得できない場合の最終フォールバック値のみ。
    # 通常の起動ポートは app_setting テーブル（server.port）から取得する。
    fallback_server_port: int = 8100


def get_settings() -> Settings:
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
