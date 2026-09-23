"""アプリアイコン（`app/assets/michinari.ico`・`frontend/public/favicon.png`）の生成スクリプト。

exe のアイコン・システムトレイのアイコン・通知（トースト）の送信元アイコン・ブラウザの
ファビコンは同一の絵柄を使う。その絵柄はミチナリのキャラクターアイコン（UI-01「通常時」、
`docs/icons/01_通常時.png`）の頭部（黄色い顔＋白いセンターライン＋双葉）を切り出したもので
あり、**切り出し範囲の定義を2箇所に持たない**ために、本スクリプトが1回の切り出しから
`.ico`とファビコンPNGの両方を書き出す（CLAUDE.md DRYの原則）。

小サイズ（16〜32px）では全身イラスト（背景の街並み等を含む）は細部が潰れて視認性が落ちる
ため、キャラクターの頭部のみを正方形に切り出して使う（仕様書v1.1 13章、アイコンセット
仕様書v1.0 19章。2026-09-23、旧デザイン「道なりの矢印」から刷新）。

`.ico`・favicon.pngはいずれもバイナリのためリポジトリへ commit する（ビルド時に生成すると、
Pillow を持たない環境でビルドできなくなる）。絵柄を変える必要が生じたときだけ本スクリプトを
実行し直し、生成物を commit する。

    cd backend
    uv run python scripts/generate_icon.py
"""

import sys
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.desktop.assets import resolve_icon_path  # noqa: E402 (sys.path調整の後に取り込む)

#: 切り出し元。`docs/icons/`はキャラクターアイコン11種（512px版）の原本置き場
#: （アイコンセット仕様書v1.0 19章）で、UI-01「通常時」を使う。
SOURCE_IMAGE_PATH = REPO_ROOT / "docs" / "icons" / "01_通常時.png"

#: 頭部の切り出し範囲（left, top, right, bottom）。512x512の元画像に対する座標。
#: 顔・センターライン・双葉の全体が収まり、16pxまで縮小しても表情と双葉の形が判別できる
#: 範囲を目視で確認して決めた（このファイルの生成時に16/24/32/48pxで確認済み）。
HEAD_CROP_BOX = (55, 15, 355, 315)

#: 書き出し先。アプリが実際に読む場所（`app/desktop/assets.py`）をそのまま使い、
#: ファイル名・配置先を書き写さない。書き写すと、名前を変えたときに生成先だけが古いまま
#: 残り、トレイ・通知・exeのアイコンが静かに欠落する（`tray.load_icon_image`が代替画像へ
#: フォールバックするため気づきにくい）。
ICON_OUTPUT_PATH = resolve_icon_path()

#: ブラウザのファビコン書き出し先（`frontend/index.html`の`<link rel="icon">`が参照する）。
FAVICON_OUTPUT_PATH = REPO_ROOT / "frontend" / "public" / "favicon.png"

#: `.ico`へ収める画素数。Windowsはタスクバー・通知・エクスプローラで異なるサイズを要求する
#: ため、拡大縮小で滲まないよう主要サイズを全て持たせる。
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

#: favicon.pngの画素数。ブラウザ側で必要に応じて縮小表示されるため1枚のみで足りる。
FAVICON_SIZE = 256


def load_head_crop() -> Image.Image:
    """UI-01（通常時）の頭部を正方形に切り出す。

    返り値:
        RGBA の `PIL.Image.Image`（300x300、HEAD_CROP_BOXの寸法）。

    使用例:
        >>> load_head_crop().size
        (300, 300)
    """
    source = Image.open(SOURCE_IMAGE_PATH).convert("RGBA")
    return source.crop(HEAD_CROP_BOX)


def generate(
    icon_output_path: Path = ICON_OUTPUT_PATH,
    favicon_output_path: Path = FAVICON_OUTPUT_PATH,
) -> tuple[Path, Path]:
    """`.ico`とfavicon.pngを、同じ頭部の切り出しから書き出す。

    引数:
        icon_output_path: `.ico`の書き出し先。既定は `app/assets/michinari.ico`。
        favicon_output_path: favicon.pngの書き出し先。既定は `frontend/public/favicon.png`。

    返り値:
        書き出した2つのパス（icon, favicon）。
    """
    head = load_head_crop()

    icon_output_path.parent.mkdir(parents=True, exist_ok=True)
    largest = head.resize((max(ICON_SIZES), max(ICON_SIZES)), Image.LANCZOS)
    largest.save(
        icon_output_path,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
        bitmap_format="png",
    )

    favicon_output_path.parent.mkdir(parents=True, exist_ok=True)
    head.resize((FAVICON_SIZE, FAVICON_SIZE), Image.LANCZOS).save(favicon_output_path, format="PNG")

    return icon_output_path, favicon_output_path


if __name__ == "__main__":  # pragma: no cover (手動実行のみ)
    icon_path, favicon_path = generate()
    print(f"生成しました: {icon_path} ({icon_path.stat().st_size:,} バイト)")
    print(f"生成しました: {favicon_path} ({favicon_path.stat().st_size:,} バイト)")
    sys.exit(0)
