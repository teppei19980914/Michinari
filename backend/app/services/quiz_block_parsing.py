"""復習クイズの問題ブロック解析の共通処理（開発Todo_単語帳_v1.0 要件B B-D3）。

テーマ由来（`quiz_generation_service`、出典は報告の日付）・単語帳由来
（`vocab_quiz_generation_service`、出典は`#カードID`）のいずれも、AI応答を「===」で
区切り、5フィールド（問題・選択肢4つ・正解・解説・出典）を抜き出す処理は共通のため、
ここへ集約する（CLAUDE.md DRYの原則）。出典の形式・実在検証は出所ごとに異なるため、
本モジュールは出典を生文字列（`citation_raw`）のまま返し、検証は呼び出し側が行う。

ReDoS対策（既存の復習クイズで検出・修正済みのCWE-1333、CRITICAL）はそのまま維持する：
`[^\\n]+?`（非貪欲・改行を跨がない）を使い`re.DOTALL`は使わない。`_MAX_BLOCK_CHARS`超の
ブロックは正規表現に通さず破棄する多層防御も維持する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 問題と問題の間の区切り（プロンプトで固定文字列として指定）。
_BLOCK_SEPARATOR = re.compile(r"^\s*===\s*$", re.MULTILINE)
#: 1ブロック分（問題文〜出典まで）を一括でマッチする正規表現。各フィールドは1行想定の
#: ため`[^\n]+?`（改行を跨がない非貪欲）で区切り、`re.DOTALL`は使わない。`.+?`を
#: `re.DOTALL`配下で連鎖させると、区切りリテラルと同じ文字列が入力中に繰り返し出現した
#: 場合に破滅的バックトラッキング（ReDoS、CWE-1333）が発生する（セキュリティレビューで
#: 実測確認。入力はAI応答であり、プロンプトに展開される利用者の報告本文・単語帳カードを
#: 経由した間接プロンプトインジェクションの影響を受けうるため信頼できない外部入力として
#: 扱う）。出典（`citation`）の形式はテーマ由来（日付）・単語帳由来（#カードID）で異なる
#: ため、ここでは形式を制約せず生文字列として抜き出す（検証は呼び出し側）。
_QUESTION_BLOCK_PATTERN = re.compile(
    r"問題:[ \t]*(?P<question>[^\n]+?)[ \t]*\n"
    r"選択肢1:[ \t]*(?P<choice1>[^\n]+?)[ \t]*\n"
    r"選択肢2:[ \t]*(?P<choice2>[^\n]+?)[ \t]*\n"
    r"選択肢3:[ \t]*(?P<choice3>[^\n]+?)[ \t]*\n"
    r"選択肢4:[ \t]*(?P<choice4>[^\n]+?)[ \t]*\n"
    r"正解:[ \t]*(?P<correct>[1-4])[ \t]*\n"
    r"解説:[ \t]*(?P<explanation>[^\n]+?)[ \t]*\n"
    r"出典:[ \t]*(?P<citation>[^\n]+?)[ \t]*$"
)
#: 1問として非現実的な長さのブロックは正規表現に通さず破棄する（ReDoS対策の多層防御。
#: 上記のパターン自体の安全性で構造的には解消済みだが、想定外の入力に対する保険として残す）。
_MAX_BLOCK_CHARS = 2000


@dataclass(frozen=True)
class ParsedQuestionBlock:
    question_text: str
    choices: list[str]
    correct_choice_index: int
    explanation: str
    #: 出典の生文字列（検証・変換は呼び出し側が行う）。
    citation_raw: str


#: シチュエーションカード由来の誤答生成（開発Todo_単語帳_v1.0 要件F F-D11）。問題文・正解・
#: 解説はAIに作らせず登録済みの文をそのまま使うため、AIには「出典→誤答1→誤答2→誤答3」の
#: 4行だけを出力させる（既存のParsedQuestionBlock・7フィールドの形式とは異なる）。
#: ReDoS対策（`[^\n]+?`・`re.DOTALL`不使用）は既存と同じ方針を共有する。
_DISTRACTOR_BLOCK_PATTERN = re.compile(
    r"出典:[ \t]*(?P<citation>[^\n]+?)[ \t]*\n"
    r"誤答1:[ \t]*(?P<distractor1>[^\n]+?)[ \t]*\n"
    r"誤答2:[ \t]*(?P<distractor2>[^\n]+?)[ \t]*\n"
    r"誤答3:[ \t]*(?P<distractor3>[^\n]+?)[ \t]*$"
)


@dataclass(frozen=True)
class ParsedDistractorBlock:
    #: 出典の生文字列（検証・変換は呼び出し側が行う）。
    citation_raw: str
    distractors: list[str]


def parse_distractor_blocks(response_text: str) -> list[ParsedDistractorBlock]:
    """シチュエーションカード由来の誤答生成の応答を解析する（開発Todo_単語帳_v1.0 要件F）。

    `parse_question_blocks`と区切り（`===`）・ブロック長上限（`_MAX_BLOCK_CHARS`）を共有し、
    フィールド構成（出典→誤答1〜3の4行）が異なるため解析用の正規表現・データクラスは分ける
    （F-D11）。形式に合わないブロックは個別に無視する。
    """
    parsed: list[ParsedDistractorBlock] = []
    for block in _BLOCK_SEPARATOR.split(response_text):
        if len(block) > _MAX_BLOCK_CHARS:
            continue
        match = _DISTRACTOR_BLOCK_PATTERN.search(block)
        if match is None:
            continue
        parsed.append(
            ParsedDistractorBlock(
                citation_raw=match.group("citation").strip(),
                distractors=[
                    match.group("distractor1").strip(),
                    match.group("distractor2").strip(),
                    match.group("distractor3").strip(),
                ],
            )
        )
    return parsed


def parse_question_blocks(response_text: str) -> list[ParsedQuestionBlock]:
    """応答を「===」で分割し、ブロックごとに5フィールドを抽出する。

    形式に合わないブロックは個別に無視する（1ブロックの不正でバッチ全体を無効にしない）。
    出典の実在検証（日付・カードIDの集合照合）は行わない（呼び出し側の責務）。
    """
    parsed: list[ParsedQuestionBlock] = []
    for block in _BLOCK_SEPARATOR.split(response_text):
        if len(block) > _MAX_BLOCK_CHARS:
            continue
        match = _QUESTION_BLOCK_PATTERN.search(block)
        if match is None:
            continue
        parsed.append(
            ParsedQuestionBlock(
                question_text=match.group("question").strip(),
                choices=[
                    match.group("choice1").strip(),
                    match.group("choice2").strip(),
                    match.group("choice3").strip(),
                    match.group("choice4").strip(),
                ],
                correct_choice_index=int(match.group("correct")) - 1,
                explanation=match.group("explanation").strip(),
                citation_raw=match.group("citation").strip(),
            )
        )
    return parsed
