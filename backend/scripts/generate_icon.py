"""アプリアイコン（`app/assets/michinari.ico`）の生成スクリプト。

exe のアイコン・システムトレイのアイコン・通知（トースト）の送信元アイコンは同一の絵柄を
使う。その絵柄は画面のファビコン（`frontend/public/favicon.svg`）と同じ「道なりの矢印」で
あり、**形の定義を2箇所に持たない**ために、本スクリプトがファビコンのパス形状を写した
頂点列から`.ico`を生成する（CLAUDE.md DRYの原則）。

`.ico`はバイナリのためリポジトリへ commit する（ビルド時に生成すると、Pillow を持たない
環境でビルドできなくなる）。絵柄を変える必要が生じたときだけ本スクリプトを実行し直し、
生成物を commit する。

    cd backend
    uv run python scripts/generate_icon.py

なぜSVGをそのまま変換しないか: SVGラスタライザ（cairosvg 等）は外部ライブラリの追加を
伴ううえ、Windowsではネイティブ依存の導入が必要になる。アイコンは年に何度も変わるもの
ではないため、ビルド依存を増やさずに済む頂点列方式を採る（技術選定書2章「依存を増やさない」）。
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.desktop.assets import resolve_icon_path  # noqa: E402 (sys.path調整の後に取り込む)

#: 書き出し先。アプリが実際に読む場所（`app/desktop/assets.py`）をそのまま使い、
#: ファイル名・配置先を書き写さない。書き写すと、名前を変えたときに生成先だけが古いまま
#: 残り、トレイ・通知・exeのアイコンが静かに欠落する（`tray.load_icon_image`が代替画像へ
#: フォールバックするため気づきにくい）。
OUTPUT_PATH = resolve_icon_path()

#: ファビコン（frontend/public/favicon.svg）の外形パスを写した頂点列。SVGのviewBoxが
#: 48x46 のため、座標もその空間で表す。パス中の小さな角丸（半径1〜2）は頂点へ畳んで
#: いる（16〜256pxへ縮小すると視覚的な差は出ないため）。
ICON_VIEWBOX = (48.0, 46.0)
ICON_OUTLINE = [
    (25.946, 44.938),
    (23.925, 44.240),
    (23.925, 33.937),
    (21.663, 31.675),
    (10.287, 31.675),
    (9.367, 29.887),
    (16.847, 19.416),
    (15.005, 15.838),
    (1.237, 15.838),
    (0.317, 14.050),
    (10.013, 0.474),
    (10.933, 0.000),
    (39.827, 0.000),
    (40.747, 1.788),
    (33.267, 12.259),
    (35.109, 15.838),
    (46.486, 15.838),
    (47.376, 17.668),
]

#: ファビコンの塗り色（favicon.svg の fill="#863bff"）。明色・暗色どちらのタスクバーでも
#: 視認できるため、トレイ用に色を変えることはしない。
ICON_FILL = (134, 59, 255, 255)

#: `.ico`へ収める画素数。Windowsはタスクバー・通知・エクスプローラで異なるサイズを要求する
#: ため、拡大縮小で滲まないよう主要サイズを全て持たせる。
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

#: 縁を滑らかにするための描画倍率（この倍率で描いてから縮小する）。Pillowの多角形塗りは
#: アンチエイリアスを行わないため、超過サンプリングで代替する。
SUPERSAMPLE = 8


def render_icon(size: int) -> Image.Image:
    """指定画素数の正方形アイコンを1枚描画する（背景は透過）。

    引数:
        size: 出力する一辺の画素数。

    返り値:
        RGBA の `PIL.Image.Image`。

    使用例:
        >>> render_icon(32).size
        (32, 32)
    """
    view_width, view_height = ICON_VIEWBOX
    canvas = size * SUPERSAMPLE
    # 縦横比を保ったまま canvas へ収め、余白を均等に振り分ける。
    scale = min(canvas / view_width, canvas / view_height)
    offset_x = (canvas - view_width * scale) / 2
    offset_y = (canvas - view_height * scale) / 2

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(image).polygon(
        [(x * scale + offset_x, y * scale + offset_y) for x, y in ICON_OUTLINE], fill=ICON_FILL
    )
    return image.resize((size, size), Image.LANCZOS)


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    """全サイズを描画し、1つの`.ico`として書き出す。

    引数:
        output_path: 書き出し先。既定は `app/assets/michinari.ico`。

    返り値:
        書き出したパス。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    largest = render_icon(max(ICON_SIZES))
    largest.save(
        output_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES], bitmap_format="png"
    )
    return output_path


if __name__ == "__main__":  # pragma: no cover (手動実行のみ)
    path = generate()
    print(f"生成しました: {path} ({path.stat().st_size:,} バイト)")
    sys.exit(0)
