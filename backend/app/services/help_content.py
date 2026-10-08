"""ヘルプ本文の読み込み（Phase43、開発Todo U8）。

本文の正は `frontend/src/locales/ja.json` の `help` 名前空間であり、
`scripts/export_help_content.py` が書き出した生成物（`app/content/help_content.json`）を
読むだけである。実行時に frontend を参照しないため、配布物にもそのまま同梱できる。
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: 生成物の場所（`scripts/export_help_content.py` の `OUTPUT_PATH` と一致させる）。
HELP_CONTENT_PATH = Path(__file__).resolve().parents[1] / "content" / "help_content.json"


@dataclass(frozen=True)
class HelpSection:
    """ヘルプの1セクション。`id` は出典行で参照するセクションID
    （ja.json の help.sections のキー）。"""

    id: str
    title: str
    body: tuple[str, ...]


@lru_cache(maxsize=1)
def load_sections() -> tuple[HelpSection, ...]:
    """生成物を読み、セクションの一覧を返す（読み込みは1回だけ行う）。

    返り値はヘルプの定義順。出典検証（実在するIDか）の基準にも使う。
    """
    raw = json.loads(HELP_CONTENT_PATH.read_text(encoding="utf-8"))
    return tuple(
        HelpSection(id=section["id"], title=section["title"], body=tuple(section["body"]))
        for section in raw["sections"]
    )
