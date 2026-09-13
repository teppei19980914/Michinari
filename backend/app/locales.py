"""バックエンドが表示する文言の解決（CODING_RULES.md「画面のラベル・ボタン文言」）。

通常、サーバは文言を持たない。エラーはコードだけを返し、日本語はフロントエンドが
`frontend/src/locales/ja.json` から引く（技術選定書7.3）。ただしシステムトレイのメニューと
デスクトップ通知（トースト）は**Pythonプロセスが直接画面へ出す文言**であり、フロントエンドを
経由しない。そこでこのモジュールが、フロントエンドと**同じ`ja.json`**を読んで解決する。

バックエンド用に別のロケールファイルを作らないのは、日本語の文言が2ファイルへ分かれると
言い回しの統一が崩れ、片方だけ直す事故が起きるためである（CLAUDE.md DRYの原則）。
`ja.json`が単一の情報源であり、配布パッケージにはビルド時に同梱する
（`scripts/build_package.py`の`build_backend`）。

解決規則は`frontend/src/locales/t.ts`と同じにしてある（ドット区切りで辿り、文字列に
辿り着かなければキーをそのまま返す。`{{name}}`を変数で置換する）。片方だけ規則が変わると
同じキーが画面とトレイで違う結果になるため、変更時は両方を合わせること。
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, resolve_bundled_path
from app.constants.bundle import LOCALES_DIR_NAME

#: 表示言語。`app_setting`の`display.locale`は現時点で"ja"のみを許容するため
#: （`settings_service._ALLOWED_LOCALES`）、読み込むファイルも1つに固定する。
#: 言語を増やす際は、この定数ではなく`display.locale`を見て切り替えるよう拡張する。
DEFAULT_LOCALE = "ja"


def resolve_locale_path(locale: str = DEFAULT_LOCALE) -> Path:
    """ロケールファイルの配置先を解決する（配布パッケージ対応）。

    配布パッケージでは同梱物を、ソースから起動する開発環境ではフロントエンドの
    リポジトリ内の原本を参照する。

    引数:
        locale: 言語コード。既定は`DEFAULT_LOCALE`。

    返り値:
        ロケールJSONのパス（存在するとは限らない。判定は`load_messages`が行う）。
    """
    filename = f"{locale}.json"
    return resolve_bundled_path(
        f"{LOCALES_DIR_NAME}/{filename}",
        REPO_ROOT / "frontend" / "src" / "locales" / filename,
    )


@cache
def load_messages(locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
    """ロケールファイルを読み込む（プロセス内で1度だけ）。

    ファイルが無い・壊れている場合は空の辞書を返す。トレイや通知の文言が出せないことは
    アプリの起動を止めるほどの障害ではなく、`t`がキー文字列を返して動作を続けられるため
    （同梱漏れはビルドのテストで検出する。`tests/test_desktop_locales.py`）。

    引数:
        locale: 言語コード。

    返り値:
        入れ子の辞書。読み込めなければ空辞書。
    """
    path = resolve_locale_path(locale)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def t(key: str, locale: str = DEFAULT_LOCALE, **variables: object) -> str:
    """ドット区切りキーで文言を取得する（`frontend/src/locales/t.ts`と同じ規則）。

    引数:
        key: `desktop.tray.open`のようなドット区切りキー。
        locale: 言語コード。
        **variables: `{{name}}`形式の差し込み変数。

    返り値:
        解決した文言。文字列に辿り着けない場合はキーをそのまま返す
        （画面が空欄になるより、どのキーが未定義かが分かるほうが直しやすいため）。

    使用例:
        >>> t("desktop.tray.quit")
        '終了'
    """
    node: Any = load_messages(locale)
    for part in key.split("."):
        if not isinstance(node, dict):
            return key
        node = node.get(part)
    if not isinstance(node, str):
        return key
    text = node
    for name, value in variables.items():
        text = text.replace(f"{{{{{name}}}}}", str(value))
    return text
