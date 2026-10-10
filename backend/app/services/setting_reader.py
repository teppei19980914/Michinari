"""app_setting からの型付き読み出し（CODING_RULES.md: 閾値・パラメータは app_setting へ外部化）。

value は文字列で保存されているため（設計書 データ構造編 5.2）、value_type に応じてここで変換する。
変換ロジックを呼び出し側に重複させないための共通窓口。
"""

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import DISPLAY_LOCALE
from app.models.setting import AppSetting
from app.services.exceptions import AppSettingNotFoundError


def _get_row(session: Session, key: str) -> AppSetting:
    row = session.get(AppSetting, key)
    if row is None:
        raise AppSettingNotFoundError(key)
    return row


def get_str(session: Session, key: str) -> str:
    return _get_row(session, key).value


def get_int(session: Session, key: str) -> int:
    return int(_get_row(session, key).value)


def get_float(session: Session, key: str) -> float:
    return float(_get_row(session, key).value)


def get_bool(session: Session, key: str) -> bool:
    return _get_row(session, key).value.strip().lower() == "true"


def is_english_locale(session: Session) -> bool:
    """`display.locale`が英語かどうか（日英i18n対応、2026-10）。

    AI応答言語の指示追記（`app/ai/orchestration.py`）とAIプロンプトのデータ部分の
    語彙切替（`app/services/ai_context_service.py`）の両方から使う判定で、
    DRYの原則により1箇所へ集約する。

    `en`以外は全てja扱いにする除外リスト方式であり、フロントエンドの`t.ts`の`isLocale`
    （ja/en以外を明示的に弾く許可リスト方式）とは判定の組み方が非対称である。ただし
    `display.locale`は`settings_service._ALLOWED_LOCALES`の書き込み時検証により
    ja/en以外の値がDBへ入ることは正規の経路では起きないため、挙動上の差異は生じない
    （test-coverage-reviewerレビュー、2026-10確認）。"""
    return get_str(session, DISPLAY_LOCALE) == "en"
