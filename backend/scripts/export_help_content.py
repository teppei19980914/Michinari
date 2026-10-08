"""ヘルプ本文（`frontend/src/locales/ja.json` の `help.sections`）をバックエンド用JSONへ書き出す。

ヘルプAIアシスタント（Phase43、開発Todo U8）が答えの根拠とするヘルプ本文の生成スクリプト。
正の情報源は `ja.json` の `help` 名前空間のみで、本ファイルは生成物を書き出すだけである。
生成物 `app/content/help_content.json` は版管理に含め、`tests/test_help_content.py` が
`ja.json` との不一致（書き出し忘れ）を検出する。

使い方（`backend` で実行）:
    uv run python scripts/export_help_content.py
"""

import json
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
JA_JSON_PATH = BACKEND_ROOT.parent / "frontend" / "src" / "locales" / "ja.json"
OUTPUT_PATH = BACKEND_ROOT / "app" / "content" / "help_content.json"

#: 見出しのキー（各セクションの `title`）。本文は見出し以外の文字列を、定義順に集める。
_TITLE_KEY = "title"


def _collect_body(node: Any) -> list[str]:
    """セクションの本文を定義順に集める（ネストした辞書も再帰で辿り、文字列をすべて集める）。

    `promptVariables` のように `purposes`（用途ごとの辞書）を持つセクションにも対応する。
    JSONの辞書はキーの挿入順を保つため、出力は同じ入力から常に同じになる。
    """
    texts: list[str] = []
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        for value in node.values():
            texts.extend(_collect_body(value))
    return texts


def build_help_content(ja: dict[str, Any]) -> dict[str, Any]:
    """`ja.json` の内容から、バックエンド用のヘルプ本文（セクションID・見出し・本文）を組み立てる。

    引数: ja.json を読み込んだ辞書（`help` 名前空間を含むこと）。
    返り値: `{"sections": [{"id", "title", "body"}, ...]}`。
    """
    sections = ja["help"]["sections"]
    return {
        "sections": [
            {
                "id": section_id,
                "title": section[_TITLE_KEY],
                # 最上位の見出しは別に持つため本文から外す（ネストした見出しは本文に残す）
                "body": _collect_body({k: v for k, v in section.items() if k != _TITLE_KEY}),
            }
            for section_id, section in sections.items()
        ]
    }


def render(content: dict[str, Any]) -> str:
    """生成物の文字列表現（UTF-8・インデント2・末尾改行）。比較と書き出しで同じ表現を使う。"""
    return json.dumps(content, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    ja = json.loads(JA_JSON_PATH.read_text(encoding="utf-8"))
    OUTPUT_PATH.write_text(render(build_help_content(ja)), encoding="utf-8")
    print(f"書き出しました: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
