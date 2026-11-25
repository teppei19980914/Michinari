"""schedule_revision_block_parsing の単体テスト（開発Todo_スケジュール・ガントチャート_v1.1
13.4・13.10、単位5）。"""

import time

from app.services import schedule_revision_block_parsing as parsing

_MAX_BLOCK_CHARS = 2000


def _parse(text: str):
    return parsing.parse_response(text, max_block_chars=_MAX_BLOCK_CHARS)


def test_parse_response_parses_change_and_warning_blocks_and_summary():
    text = (
        "種類: 変更\n"
        "行ID: 12\n"
        "予定開始日: 2026-11-20\n"
        "予定終了日: 2026-11-25\n"
        "理由: 遅れているため\n"
        "===\n"
        "種類: 注意\n"
        "行ID: 15\n"
        "理由: 期限内に収まりません\n"
        "===\n"
        "総評: 全体的に少し遅れています"
    )

    result = _parse(text)

    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.item_id_raw == "12"
    assert change.planned_start_date_raw == "2026-11-20"
    assert change.planned_end_date_raw == "2026-11-25"
    assert change.reason == "遅れているため"

    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.item_id_raw == "15"
    assert warning.reason == "期限内に収まりません"

    assert result.summary == "全体的に少し遅れています"


def test_parse_response_returns_empty_when_only_summary():
    result = _parse("総評: 修正が必要な行はありませんでした")

    assert result.changes == []
    assert result.warnings == []
    assert result.summary == "修正が必要な行はありませんでした"


def test_parse_response_returns_all_empty_for_blank_input():
    result = _parse("")

    assert result.changes == []
    assert result.warnings == []
    assert result.summary is None


def test_parse_response_ignores_malformed_block_but_keeps_others():
    """1ブロックの形式崩れが他のブロックを無効にしない（13.5「他のブロックは生かす」）。"""
    text = (
        "種類: 変更\n"
        "行ID: 12\n"
        "理由: 日付が無い（形式崩れ）\n"
        "===\n"
        "種類: 変更\n"
        "行ID: 13\n"
        "予定開始日: 2026-11-20\n"
        "予定終了日: 2026-11-25\n"
        "理由: 正常なブロック\n"
    )

    result = _parse(text)

    assert len(result.changes) == 1
    assert result.changes[0].item_id_raw == "13"


def test_parse_response_discards_oversized_block():
    """1ブロックの文字数上限超はブロックごと正規表現に通さず破棄する（ReDoS対策の多層防御）。"""
    oversized = (
        "種類: 変更\n"
        "行ID: 12\n"
        "予定開始日: 2026-11-20\n"
        "予定終了日: 2026-11-25\n"
        "理由: " + "あ" * _MAX_BLOCK_CHARS
    )

    result = _parse(oversized)

    assert result.changes == []


def test_parse_response_takes_only_the_first_summary():
    text = "総評: 最初の総評\n===\n総評: 2番目の総評（採用されない）"

    result = _parse(text)

    assert result.summary == "最初の総評"


def test_parse_response_does_not_hang_on_adversarial_repetition_in_change_blocks():
    """セキュリティレビューで想定されるReDoS（CWE-1333）の回帰テスト。

    `quiz_block_parsing`と同じ対策（`[^\\n]+?`・非貪欲・`re.DOTALL`不使用）を
    schedule_revision_block_parsing でも維持していることを確認する。区切りリテラル
    （`予定開始日:`等）を含む行を大量に繰り返す応答（間接プロンプトインジェクションや
    AIの反復出力の故障モードを想定）を渡しても、破滅的バックトラッキングで無限に近い
    時間停止しないことを確認する（1秒以内に完了）。
    """
    repeat_unit = "予定開始日: x\n予定終了日: x\n理由: x\n"
    adversarial = "種類: 変更\n行ID: 1\n" + repeat_unit * 80
    assert len(adversarial) < _MAX_BLOCK_CHARS

    started = time.monotonic()
    result = _parse(adversarial)
    elapsed = time.monotonic() - started

    assert result.changes == []
    assert elapsed < 1.0


def test_parse_response_does_not_hang_on_adversarial_repetition_in_warning_blocks():
    repeat_unit = "行ID: x\n理由: x\n"
    adversarial = "種類: 注意\n" + repeat_unit * 100
    assert len(adversarial) < _MAX_BLOCK_CHARS

    started = time.monotonic()
    result = _parse(adversarial)
    elapsed = time.monotonic() - started

    assert result.warnings == []
    assert elapsed < 1.0
