"""AI応答の「===」区切りブロック解析の共通処理（`quiz_block_parsing.py`・
`schedule_revision_block_parsing.py`で重複していた区切り正規表現と文字数上限ガードを
集約、CLAUDE.md DRYの原則）。

フィールド構成（問題・選択肢4つ...、種類・行ID...等）は用途ごとに異なるため、ブロックへの
分割と長さ上限による多層防御のみをここに置き、フィールド抽出の正規表現は呼び出し側が持つ。
"""

from __future__ import annotations

import re

#: ブロックの区切り（プロンプトで固定文字列として指定）。
BLOCK_SEPARATOR = re.compile(r"^\s*===\s*$", re.MULTILINE)


def split_blocks(response_text: str, *, max_block_chars: int) -> list[str]:
    """応答を`BLOCK_SEPARATOR`で分割し、1ブロックとして非現実的な長さのブロックを除く。

    ReDoS対策の多層防御（CWE-1333、既存の復習クイズで検出・修正済み）。超過ブロックは
    フィールド抽出の正規表現に一切通さない。
    """
    return [
        block for block in BLOCK_SEPARATOR.split(response_text) if len(block) <= max_block_chars
    ]
