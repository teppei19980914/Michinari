"""OpenAPIスキーマを静的ファイルへ出力する(technical選定書4.4「型の共有方針」)。

frontend側のnpm scripts（generate:api-types）から呼び出し、
openapi-typescriptの入力ファイルとして使う。サーバ起動不要で型生成できるようにするため、
実サーバへの接続ではなくFastAPIアプリのopenapi()を直接呼び出す。
"""

import json
from pathlib import Path

from app.main import app

_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    _OUTPUT_PATH.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
