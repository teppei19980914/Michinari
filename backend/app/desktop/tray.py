"""通知領域（システムトレイ）のアイコンとメニュー（実装スコープA、Phase37）。

トレイには`pystray`（LGPL-3.0）を使う。Windowsでは win32 バックエンドが選ばれ、全機能が
利用できると公式が明記している（https://pystray.readthedocs.io/en/latest/usage.html ）。

**`Icon.run()`はメインスレッドで呼ぶ必要がある**（同公式。ウィンドウメッセージのループを
回すため）。そのため本アプリでは、Webサーバ（uvicorn）のほうを別スレッドへ回している
（`app/desktop/runner.py`）。

アイコンの**左クリック1回**で既定の動作（画面を開く）が起きる。pystrayのwin32実装が
`WM_LBUTTONUP`で既定動作を呼ぶためで、ダブルクリックを待つ仕組みは無い
（`pystray/_win32.py`）。ダブルクリックしても開くが、2回押した分だけタブが開く。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pystray
from PIL import Image

from app.constants import locale_keys
from app.locales import t

logger = logging.getLogger(__name__)

#: pystrayがアイコンを識別する内部名（画面には出ない）。
TRAY_ICON_NAME = "michinari"

#: アイコン画像を読み込めなかった場合に描く代替画像の大きさと色。アイコンが無くても
#: 常駐と終了ができるようにするための保険であり、通常は使われない。
FALLBACK_ICON_SIZE = (64, 64)
FALLBACK_ICON_COLOR = (134, 59, 255, 255)


def load_icon_image(icon_path: Path) -> Image.Image:
    """トレイに表示する画像を読み込む。

    引数:
        icon_path: `.ico`のパス。

    返り値:
        `PIL.Image.Image`。読み込めない場合は単色の代替画像
        （アイコンが欠けただけでアプリを起動できなくしないため）。
    """
    try:
        return Image.open(icon_path)
    except OSError:
        logger.warning("アイコンを読み込めませんでした。代替の画像を使います: %s", icon_path)
        return Image.new("RGBA", FALLBACK_ICON_SIZE, FALLBACK_ICON_COLOR)


def build_icon(on_open: Callable[[], None], on_quit: Callable[[], None], icon_path: Path):
    """トレイアイコンを組み立てる（まだ表示はしない）。

    引数:
        on_open: 「ミチナリを開く」および左クリックで呼ぶ処理。
        on_quit: 「終了」で呼ぶ処理。
        icon_path: アイコン画像のパス。

    返り値:
        `pystray.Icon`。`run()`で表示が始まる。
    """
    icon = pystray.Icon(
        TRAY_ICON_NAME,
        icon=load_icon_image(icon_path),
        title=t(locale_keys.TRAY_TOOLTIP),
        menu=pystray.Menu(
            # default=True の項目は、Windowsではアイコンの左クリックでも呼ばれる。
            pystray.MenuItem(t(locale_keys.TRAY_OPEN), lambda *_: on_open(), default=True),
            pystray.MenuItem(t(locale_keys.TRAY_QUIT), lambda *_: on_quit()),
        ),
    )
    return icon
