"""同梱ライブラリのライセンス表記を配布パッケージへ集める（Phase37）。

本アプリは公開リポジトリのGitHub Releasesで配布するため、同梱するライブラリのライセンス
義務は**全世界への頒布**として発生する。とりわけ `pystray`（システムトレイ）は
**LGPL-3.0** であり、次の3点が求められる（LGPL-3.0 第4条）。

1. ライブラリを使用している旨と適用ライセンスを明示する
   → `NOTICES.txt` を配布物へ同梱する（本スクリプト）
2. GNU GPL と LGPL の全文を添付する
   → `THIRD_PARTY_LICENSES/` へ原本を複製する（本スクリプト）
3. 利用者が改変版ライブラリへ差し替えられるようにする
   → pystray を exe へ埋め込まず `_internal/pystray/` へ素のファイルとして置く
     （`build_package.pyinstaller_args` の `--exclude-module`／`--add-data`）

ライセンス本文は各パッケージが `dist-info` に同梱しているものをそのまま複製する
（本文を書き写すと、パッケージ更新時に古い版が残るため。CLAUDE.md DRYの原則）。

実行はビルドから自動で行われる（`build_package.assemble_launcher`）。単体で試すときは:

    cd backend
    uv run python scripts/collect_licenses.py <出力先ディレクトリ>
"""

import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

#: 配布物へ作るフォルダ名とお知らせファイル名。
LICENSES_DIR_NAME = "THIRD_PARTY_LICENSES"
NOTICES_FILE_NAME = "NOTICES.txt"


@dataclass(frozen=True)
class BundledLibrary:
    """配布パッケージへ同梱するライブラリと、その表記に必要な情報。

    属性:
        distribution: PyPI上の配布名（`importlib.metadata` で参照する名前）。
        license_name: ライセンス名（表記用）。
        license_files: `dist-info` 配下のライセンスファイル名（複数可）。
        note: 利用者向けの補足（差し替え手順など）。
    """

    distribution: str
    license_name: str
    license_files: tuple[str, ...]
    note: str = ""


#: 同梱物のうち、ライセンス表記が必要なもの。推移的な依存も含めて明示的に列挙する
#: （自動収集にすると、収集漏れが静かに起きたことに気付けないため）。
BUNDLED_LIBRARIES: tuple[BundledLibrary, ...] = (
    BundledLibrary(
        "pystray",
        "GNU Lesser General Public License v3.0 (LGPL-3.0)",
        ("COPYING", "COPYING.LGPL"),
        note=(
            "このライブラリは LGPL-3.0 です。改変版へ差し替えたい場合は、"
            "Michinari フォルダ内の _internal\\pystray\\ にあるファイルを置き換えてください"
            "（実行ファイルへ埋め込んでいないため、差し替えたものがそのまま使われます）。"
            "ソースコードは https://github.com/moses-palmer/pystray から入手できます。"
        ),
    ),
    BundledLibrary("pillow", "MIT-CMU License", ("licenses/LICENSE",)),
    BundledLibrary("windows-toasts", "Apache License 2.0", ("licenses/LICENSE",)),
    BundledLibrary("six", "MIT License", ("LICENSE",)),
)

#: `NOTICES.txt` の前書き。
_NOTICES_HEADER = f"""ミチナリ（Michinari）が使用しているソフトウェアについて

本アプリケーションには、以下のオープンソースソフトウェアが含まれています。
それぞれのライセンス全文は、同じフォルダ内の {LICENSES_DIR_NAME}\\ に収めています。

"""


def _distribution_root(distribution: str) -> Path:
    """インストール済み配布物の `dist-info` ディレクトリを返す。

    引数:
        distribution: PyPI上の配布名。

    返り値:
        `*.dist-info` のパス。

    例外:
        FileNotFoundError: `dist-info` を特定できない場合。
    """
    files = metadata.distribution(distribution).files or []
    for entry in files:
        parts = Path(str(entry)).parts
        if parts and parts[0].endswith(".dist-info"):
            return Path(str(metadata.distribution(distribution).locate_file(parts[0])))
    raise FileNotFoundError(f"{distribution} の dist-info が見つかりません")


def collect(output_dir: Path, libraries: tuple[BundledLibrary, ...] = BUNDLED_LIBRARIES) -> Path:
    """ライセンス全文とお知らせファイルを出力先へ書き出す。

    引数:
        output_dir: 配布パッケージのフォルダ（この直下へ作る）。
        libraries: 対象ライブラリ。

    返り値:
        生成した `NOTICES.txt` のパス。

    例外:
        FileNotFoundError: ライセンスファイルが見つからない場合（表記漏れのまま配布しない
            ため、警告ではなく失敗にする）。
    """
    licenses_dir = output_dir / LICENSES_DIR_NAME
    licenses_dir.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    for library in libraries:
        version = metadata.version(library.distribution)
        root = _distribution_root(library.distribution)
        copied: list[str] = []
        for relative in library.license_files:
            source = root / relative
            if not source.is_file():
                raise FileNotFoundError(f"{library.distribution} の {relative} が見つかりません")
            destination_name = f"{library.distribution}-{Path(relative).name}"
            (licenses_dir / destination_name).write_bytes(source.read_bytes())
            copied.append(destination_name)

        lines = [
            f"- {library.distribution} {version}",
            f"  ライセンス: {library.license_name}",
            f"  全文: {LICENSES_DIR_NAME}\\{', '.join(copied)}",
        ]
        if library.note:
            lines.append(f"  補足: {library.note}")
        sections.append("\n".join(lines))

    notices_path = output_dir / NOTICES_FILE_NAME
    notices_path.write_text(_NOTICES_HEADER + "\n\n".join(sections) + "\n", encoding="utf-8")
    return notices_path


if __name__ == "__main__":  # pragma: no cover (手動実行のみ)
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    path = collect(target)
    print(f"生成しました: {path}")
