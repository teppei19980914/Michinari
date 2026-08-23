"""app_setting からの型付き読み出し（CODING_RULES.md: 閾値・パラメータは app_setting へ外部化）。

value は文字列で保存されているため（設計書 データ構造編 5.2）、value_type に応じてここで変換する。
変換ロジックを呼び出し側に重複させないための共通窓口。
"""

from sqlalchemy.orm import Session

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
