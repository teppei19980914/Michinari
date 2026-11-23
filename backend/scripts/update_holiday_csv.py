"""内閣府「国民の祝日」CSVを取得・検証し、リポジトリ内のCSV・メタデータを更新する。

`release.py`の`build()`からのみ呼ぶ（開発Todo_スケジュール・ガントチャート_v1.1.md
D-43）。アプリ自体は外部通信しない方針（技術選定書6.2改訂後）を維持するため、
取得はリリース時の本スクリプトに限定する。`backend/scripts/build_package.py`単体の
実行（`uv run python scripts/build_package.py`）では呼ばれない。

検証項目（D-43）: cp932でのデコード・列数・日付の形式（いずれも
`app.services.calendar_service.parse_holiday_csv`が担う、CLAUDE.md DRYの原則）、
収録範囲の最終年が前回以上であること。いずれかに失敗した場合はリリースを中止する。

書き込んだCSV・メタデータはgit commitしない。`release.py`の`write_version`
（バージョン確定）と同じく、`build()`内で作業ツリーへ直接書き込むだけにする
（`has_uncommitted_changes`による`dirty`判定は`write_version`より前に行われるため、
この書き込みは公開の妨げにならない）。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from app.constants.bundle import (
    HOLIDAY_CSV_FILE_NAME,
    HOLIDAY_DIR_NAME,
    HOLIDAY_METADATA_FILE_NAME,
)
from app.services.calendar_service import parse_holiday_csv
from app.services.exceptions import ValidationError

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOLIDAY_SOURCE_DIR = BACKEND_DIR / "app" / "content" / HOLIDAY_DIR_NAME
HOLIDAY_CSV_PATH = HOLIDAY_SOURCE_DIR / HOLIDAY_CSV_FILE_NAME
HOLIDAY_METADATA_PATH = HOLIDAY_SOURCE_DIR / HOLIDAY_METADATA_FILE_NAME

#: 2023年に`syukujitsu.csv`から`shukujitsu.csv`へファイル名が変更された経緯がある
#: （技術選定書6.2）。その後、元のファイル名も再び利用可能になり新旧2つが並存するため、
#: 新しい方から順に試す。
HOLIDAY_CSV_URL_NEW = "https://www8.cao.go.jp/chosei/shukujitsu/shukujitsu.csv"
HOLIDAY_CSV_URL_OLD = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
HOLIDAY_CSV_URLS = (HOLIDAY_CSV_URL_NEW, HOLIDAY_CSV_URL_OLD)

#: 取得のタイムアウト（秒）。リリース作業を無期限に止めないための上限。
FETCH_TIMEOUT_SECONDS = 15.0


class HolidayCsvUpdateError(Exception):
    """祝日CSVの取得・検証に失敗したことを表す（release.py側でSystemExitへ変換する）。"""


def fetch_holiday_csv(urls: tuple[str, ...] = HOLIDAY_CSV_URLS) -> tuple[bytes, str]:
    """新旧のURLを順に試して祝日CSVを取得する。

    返り値:
        取得できたCSVのバイト列と、取得に成功したURL。

    全URLが失敗した場合は`HolidayCsvUpdateError`を送出する。
    """
    errors: list[str] = []
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
                return response.read(), url
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            errors.append(f"{url}: {exc}")
    raise HolidayCsvUpdateError(
        "祝日CSVの取得に失敗しました（新旧URLいずれも失敗）: " + " / ".join(errors)
    )


def validate_holiday_csv(csv_bytes: bytes, previous_year_to: int | None) -> tuple[int, int]:
    """取得したCSVを検証し、収録範囲（年）を返す。

    cp932デコード・列数・日付形式は`parse_holiday_csv`が検証する。ここでは追加で、
    収録範囲の最終年が前回以上であることを確認する（取得元データの異常・取得失敗時の
    不完全なレスポンスを誤って取り込まないため、D-43）。
    """
    try:
        parsed = parse_holiday_csv(csv_bytes)
    except ValidationError as exc:
        raise HolidayCsvUpdateError(f"祝日CSVの検証に失敗しました: {exc}") from exc

    years = sorted({holiday_date.year for holiday_date in parsed})
    year_from, year_to = years[0], years[-1]
    if previous_year_to is not None and year_to < previous_year_to:
        raise HolidayCsvUpdateError(
            f"取得した祝日CSVの収録最終年（{year_to}）が前回（{previous_year_to}）より"
            "後退しています。取得元データが壊れている可能性があるため中止します。"
        )
    return year_from, year_to


def _read_previous_year_to(metadata_path: Path) -> int | None:
    if not metadata_path.is_file():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    year_to = metadata.get("year_to")
    return int(year_to) if year_to is not None else None


def update_bundled_holiday_csv(
    *,
    urls: tuple[str, ...] = HOLIDAY_CSV_URLS,
    csv_path: Path = HOLIDAY_CSV_PATH,
    metadata_path: Path = HOLIDAY_METADATA_PATH,
) -> None:
    """`release.py`の`build()`から呼ぶ本体。取得・検証に失敗した場合はリリースを中止する。"""
    previous_year_to = _read_previous_year_to(metadata_path)
    try:
        csv_bytes, source_url = fetch_holiday_csv(urls)
        year_from, year_to = validate_holiday_csv(csv_bytes, previous_year_to)
    except HolidayCsvUpdateError as exc:
        raise SystemExit(f"エラー: {exc}") from exc

    csv_path.write_bytes(csv_bytes)
    metadata = {
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "source_url": source_url,
        "year_from": year_from,
        "year_to": year_to,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  → 祝日CSVを更新しました（{year_from}〜{year_to}年、取得元: {source_url}）")
