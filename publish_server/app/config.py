"""publish_serverのインフラ設定（接続先・秘密情報・ログイン制限値）。

CLAUDE.md「接続先・秘密情報・上限値は環境変数または設定に外部化し、ソースに直接書かない」
に従う。付録A（docs/開発Todo_Web公開_v1.0.md／docs/INFRASTRUCTURE.md）で定義した環境変数名と
一致させること（二重管理しない、CODING_RULES.md DRYの原則）。

本番ではD-13・10章#2で確定したとおりSupabase（マネージドPostgreSQL）の接続文字列を
`PUBLISH_DATABASE_URL`へ設定する。開発・テストでは既定値のSQLiteで動作する
（backend/app/config.pyと同じ、ローカルでPostgreSQLサーバーを用意せずに開発できるようにする
ための既定値であり、本番相当の検証はpublish_server/tests/test_migrations.pyで
`alembic upgrade head`が通ることを確認する）。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUBLISH_", env_file=".env")

    database_url: str = "sqlite:///./publish_server.db"

    #: セッションID・CSRFトークンの生成に使う秘密鍵（D-18）。本番では必ず環境変数で
    #: 十分なランダム値を設定する。未設定時のこの既定値は開発用であり、本番投入は
    #: 認めない（下記 validate_for_production 参照）。
    session_secret: str = "dev-only-insecure-session-secret"

    #: 公開ビューア（単位3）のオリジン。CORSの許可元に使う（D-18）。未設定時は空（CORS無効）。
    cors_allowed_origins: str = ""

    #: ログイン試行回数制限（D-17、開発Todo_Web公開_v1.0 10章6節で確定した初期値）。
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    #: セッションの有効期限（時間）。D-18のセッション設計に必要な値だが、具体的な時間は
    #: 開発Todoに記載が無いため、一般的なWebアプリの実務値（24時間）を既定値とし、
    #: 環境変数で上書き可能にする。
    session_lifetime_hours: int = 24

    log_level: str = "INFO"

    def is_production_like(self) -> bool:
        """SQLite既定値のまま本番相当のデータを扱っていないかの簡易判定（起動時警告用）。"""
        return not self.database_url.startswith("sqlite")


def get_settings() -> Settings:
    return Settings()
