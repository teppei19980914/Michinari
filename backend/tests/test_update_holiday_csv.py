"""`scripts/update_holiday_csv.py`のテスト（開発Todo_スケジュール・ガントチャート_v1.1.md

D-43）。ネットワークには一切接続せず、`urllib.request.urlopen`を差し替えて検証する。
"""

from __future__ import annotations

import json
import urllib.error

import pytest
import update_holiday_csv


def _csv_bytes(rows: list[tuple[str, str]]) -> bytes:
    lines = ["国民の祝日・休日月日,国民の祝日・休日名称"]
    lines.extend(f"{date_str},{name}" for date_str, name in rows)
    return ("\r\n".join(lines) + "\r\n").encode("cp932")


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def _make_urlopen(responses: dict[str, bytes | Exception]):
    def fake_urlopen(url: str, timeout: float | None = None):
        outcome = responses[url]
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResponse(outcome)

    return fake_urlopen


def test_fetch_holiday_csv_tries_the_new_url_first(monkeypatch):
    content = _csv_bytes([("2026/1/1", "元日")])
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen({update_holiday_csv.HOLIDAY_CSV_URL_NEW: content}),
    )

    result, url = update_holiday_csv.fetch_holiday_csv(
        (update_holiday_csv.HOLIDAY_CSV_URL_NEW,)
    )

    assert result == content
    assert url == update_holiday_csv.HOLIDAY_CSV_URL_NEW


def test_fetch_holiday_csv_falls_back_to_the_old_url_when_the_new_one_fails(monkeypatch):
    content = _csv_bytes([("2026/1/1", "元日")])
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen(
            {
                update_holiday_csv.HOLIDAY_CSV_URL_NEW: urllib.error.HTTPError(
                    update_holiday_csv.HOLIDAY_CSV_URL_NEW, 404, "Not Found", {}, None
                ),
                update_holiday_csv.HOLIDAY_CSV_URL_OLD: content,
            }
        ),
    )

    result, url = update_holiday_csv.fetch_holiday_csv()

    assert result == content
    assert url == update_holiday_csv.HOLIDAY_CSV_URL_OLD


def test_fetch_holiday_csv_raises_when_both_urls_fail(monkeypatch):
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen(
            {
                update_holiday_csv.HOLIDAY_CSV_URL_NEW: urllib.error.URLError("boom"),
                update_holiday_csv.HOLIDAY_CSV_URL_OLD: urllib.error.URLError("boom"),
            }
        ),
    )

    with pytest.raises(update_holiday_csv.HolidayCsvUpdateError):
        update_holiday_csv.fetch_holiday_csv()


def test_validate_holiday_csv_returns_the_year_range():
    content = _csv_bytes([("2026/1/1", "元日"), ("2027/11/23", "勤労感謝の日")])

    year_from, year_to = update_holiday_csv.validate_holiday_csv(content, None)

    assert (year_from, year_to) == (2026, 2027)


def test_validate_holiday_csv_rejects_invalid_content():
    with pytest.raises(update_holiday_csv.HolidayCsvUpdateError):
        update_holiday_csv.validate_holiday_csv(b"", None)


def test_validate_holiday_csv_rejects_a_year_to_that_regresses():
    content = _csv_bytes([("2026/1/1", "元日")])

    with pytest.raises(update_holiday_csv.HolidayCsvUpdateError):
        update_holiday_csv.validate_holiday_csv(content, previous_year_to=2027)


def test_validate_holiday_csv_accepts_a_year_to_that_advances():
    content = _csv_bytes([("2028/1/1", "元日")])

    year_from, year_to = update_holiday_csv.validate_holiday_csv(content, previous_year_to=2027)

    assert (year_from, year_to) == (2028, 2028)


def test_update_bundled_holiday_csv_writes_the_csv_and_metadata(monkeypatch, tmp_path):
    content = _csv_bytes([("2026/1/1", "元日")])
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen({update_holiday_csv.HOLIDAY_CSV_URL_NEW: content}),
    )
    csv_path = tmp_path / "holidays.csv"
    metadata_path = tmp_path / "holidays_metadata.json"

    update_holiday_csv.update_bundled_holiday_csv(
        urls=(update_holiday_csv.HOLIDAY_CSV_URL_NEW,),
        csv_path=csv_path,
        metadata_path=metadata_path,
    )

    assert csv_path.read_bytes() == content
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["year_from"] == 2026
    assert metadata["year_to"] == 2026
    assert metadata["source_url"] == update_holiday_csv.HOLIDAY_CSV_URL_NEW
    assert len(metadata["sha256"]) == 64


def test_update_bundled_holiday_csv_aborts_the_release_when_fetch_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen({update_holiday_csv.HOLIDAY_CSV_URL_NEW: urllib.error.URLError("boom")}),
    )

    with pytest.raises(SystemExit):
        update_holiday_csv.update_bundled_holiday_csv(
            urls=(update_holiday_csv.HOLIDAY_CSV_URL_NEW,),
            csv_path=tmp_path / "holidays.csv",
            metadata_path=tmp_path / "holidays_metadata.json",
        )
    assert not (tmp_path / "holidays.csv").exists()


def test_update_bundled_holiday_csv_does_not_regress_using_existing_metadata(
    monkeypatch, tmp_path
):
    metadata_path = tmp_path / "holidays_metadata.json"
    metadata_path.write_text(
        json.dumps({"year_to": 2030}),
        encoding="utf-8",
    )
    content = _csv_bytes([("2026/1/1", "元日")])
    monkeypatch.setattr(
        update_holiday_csv.urllib.request,
        "urlopen",
        _make_urlopen({update_holiday_csv.HOLIDAY_CSV_URL_NEW: content}),
    )

    with pytest.raises(SystemExit):
        update_holiday_csv.update_bundled_holiday_csv(
            urls=(update_holiday_csv.HOLIDAY_CSV_URL_NEW,),
            csv_path=tmp_path / "holidays.csv",
            metadata_path=metadata_path,
        )
    assert not (tmp_path / "holidays.csv").exists()


def test_read_previous_year_to_returns_none_when_metadata_is_missing(tmp_path):
    assert update_holiday_csv._read_previous_year_to(tmp_path / "missing.json") is None
