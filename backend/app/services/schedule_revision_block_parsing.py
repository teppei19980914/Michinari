"""AIによるスケジュール修正案の応答解析（開発Todo_スケジュール・ガントチャート_v1.1
13.4、単位5）。

`quiz_block_parsing.py`と同じく「===」の行で区切ったブロック形式とし、ReDoS対策
（`[^\\n]+?`・非貪欲・改行を跨がない、`re.DOTALL`は使わない）と1ブロックの文字数上限
（超えたブロックは正規表現に通さず破棄する多層防御）を維持する（D-66）。フィールド構成が
`quiz_block_parsing`（問題・選択肢4つ・正解・解説・出典の7フィールド固定）と異なり、
2種類のブロック（CHANGE/WARNING）と任意の総評行を持つため、専用の解析関数とする。

入力はAI応答であり、プロンプトに展開される利用者の報告本文（日次フィードバックの文脈）を
経由した間接プロンプトインジェクションの影響を受けうるため、信頼できない外部入力として
扱う（D-66）。行ID・日付の実在確認やDBとの整合検証は呼び出し側（schedule_revision_service）
の責務とし、本モジュールは文字列としての形式解析のみを行う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.ai_block_parsing_common import split_blocks

#: CHANGE（変更）ブロック：種類・行ID・予定開始日・予定終了日・理由の5フィールド。
_CHANGE_BLOCK_PATTERN = re.compile(
    r"種類:[ \t]*変更[ \t]*\n"
    r"行ID:[ \t]*(?P<item_id>[0-9]+)[ \t]*\n"
    r"予定開始日:[ \t]*(?P<planned_start_date>[^\n]+?)[ \t]*\n"
    r"予定終了日:[ \t]*(?P<planned_end_date>[^\n]+?)[ \t]*\n"
    r"理由:[ \t]*(?P<reason>[^\n]+?)[ \t]*$"
)
#: WARNING（注意）ブロック：種類・行ID・理由の3フィールド。
_WARNING_BLOCK_PATTERN = re.compile(
    r"種類:[ \t]*注意[ \t]*\n"
    r"行ID:[ \t]*(?P<item_id>[0-9]+)[ \t]*\n"
    r"理由:[ \t]*(?P<reason>[^\n]+?)[ \t]*$"
)
#: 総評（任意、1行）。CHANGE/WARNINGどちらにも一致しなかったブロックの中から探す。
_SUMMARY_PATTERN = re.compile(r"総評:[ \t]*(?P<summary>[^\n]+?)[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedChangeBlock:
    item_id_raw: str
    planned_start_date_raw: str
    planned_end_date_raw: str
    reason: str


@dataclass(frozen=True)
class ParsedWarningBlock:
    item_id_raw: str
    reason: str


@dataclass(frozen=True)
class ParsedScheduleRevisionResponse:
    changes: list[ParsedChangeBlock]
    warnings: list[ParsedWarningBlock]
    summary: str | None


def parse_response(response_text: str, *, max_block_chars: int) -> ParsedScheduleRevisionResponse:
    """応答を「===」で分割し、ブロックごとにCHANGE/WARNING/総評を抜き出す。

    形式に合わないブロックは個別に無視する（1ブロックの不正で他のブロックを無効にしない、
    13.5「形式が崩れたブロックだけを捨て、他のブロックは生かす」）。総評は最初に見つかった
    ものだけを採用する。
    """
    changes: list[ParsedChangeBlock] = []
    warnings: list[ParsedWarningBlock] = []
    summary: str | None = None

    for block in split_blocks(response_text, max_block_chars=max_block_chars):
        change_match = _CHANGE_BLOCK_PATTERN.search(block)
        if change_match is not None:
            changes.append(
                ParsedChangeBlock(
                    item_id_raw=change_match.group("item_id"),
                    planned_start_date_raw=change_match.group("planned_start_date").strip(),
                    planned_end_date_raw=change_match.group("planned_end_date").strip(),
                    reason=change_match.group("reason").strip(),
                )
            )
            continue

        warning_match = _WARNING_BLOCK_PATTERN.search(block)
        if warning_match is not None:
            warnings.append(
                ParsedWarningBlock(
                    item_id_raw=warning_match.group("item_id"),
                    reason=warning_match.group("reason").strip(),
                )
            )
            continue

        if summary is None:
            summary_match = _SUMMARY_PATTERN.search(block)
            if summary_match is not None:
                summary = summary_match.group("summary").strip()

    return ParsedScheduleRevisionResponse(changes=changes, warnings=warnings, summary=summary)
