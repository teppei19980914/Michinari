"""配布パッケージのビルドスクリプト（PyInstallerでの単一実行ファイル化、OPERATIONS.md参照）。

実行順序: テストスイートの実行（1件でも失敗すればここでビルドを中止する）→
配布バージョンをユーザ入力で確定（`backend/pyproject.toml`へ反映）→
既存パッケージのアーカイブ退避 → ビルド情報（バージョン・使用ライブラリ）の生成 →
フロントエンドの静的ビルド（`npm run build`）→ PyInstallerによるバックエンドの
パッケージ化（フロントエンドの静的ファイル・alembicマイグレーション・ビルド情報を
同梱）→ 起動用batファイル・ユーザ手順書PDFの配置 → 配布用zipの作成。

テストを最初に実行するのは、配布後に発覚した不具合（2026-08-29、exam_subject.
passing_score_type列追加マイグレーションが既存データで失敗する不具合）が、テスト
スイート自体には検出用のテストがあったにもかかわらずビルド時に実行されておらず、
そのまま配布されてしまった反省による（CODING_RULES.md「既存テーブルを変更する
マイグレーションのテスト」参照）。以後、テストが1件でも失敗する状態のビルドは
配布パッケージとして生成できない。

実行例（backendディレクトリから）: `uv run python scripts/build_package.py`
（`backend/build.bat` をダブルクリックしても同じ処理を実行できる）。

出力先: `backend/dist/Michinari/`（`Michinari.exe`・`Michinari.bat`・ユーザ手順書PDFを含む。この
フォルダごと他端末へコピーし、`Michinari.bat` をダブルクリックすれば起動できる）に加え、
同フォルダをzip化した `backend/dist/Michinari-v{version}.zip` も生成する（配布時はzipを
渡すだけでよい）。zipファイル名には確定した配布バージョンが入るため、バージョンが異なれば
過去のzipを上書きしない（同一バージョンで再ビルドした場合のみ上書きされる）。

GitHub Releasesへの公開は本スクリプトでは行わない（`scripts/publish_release.py`参照。
ビルドと公開を分離し、公開は開発者が明示的に実行する）。
"""

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from app.services.system_info_service import build_info_to_json, collect_build_info

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
APP_NAME = "Michinari"
DIST_DIR = BACKEND_DIR / "dist"
OUTPUT_DIR = DIST_DIR / APP_NAME
ARCHIVE_DIR = DIST_DIR / "_archive"
PYPROJECT_PATH = BACKEND_DIR / "pyproject.toml"
BUILD_INFO_PATH = BACKEND_DIR / "build_info.json"
#: ビルド元コミットの記録ファイル名に付ける接尾辞（配布zipと対になる名前にする）。
BUILD_COMMIT_SUFFIX = ".commit.json"
#: 配布パッケージへ同梱するユーザ手順書（`docs/`配下の原本を単一の情報源とし、
#: 配布用の複製はビルド時にここから作成する。CLAUDE.md DRYの原則）。
USER_MANUAL_PATH = REPO_ROOT / "docs" / "ユーザ手順書.pdf"
#: 配布パッケージの起動用batの元になるテンプレート（`assemble_launcher`が
#: `Michinari.bat`として複製する）。テストからも同じ実体を参照できるよう定数化する
#: （CLAUDE.md DRYの原則）。
LAUNCHER_TEMPLATE_PATH = BACKEND_DIR / "scripts" / "launcher_template.bat"
_VERSION_LINE_PATTERN = re.compile(r'(?m)^version = "[^"]*"$')
#: 半角英数字・ドット・ハイフン・アンダースコアのみ許可する。ユーザ入力をそのまま
#: pyproject.tomlのTOML文字列・zipファイル名へ埋め込むため、`"`によるTOML破損や
#: `/`・`\`によるパス区切り混入（意図しない書き込み先へのずれ）を防ぐ。
_VALID_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def archive_previous_package(
    output_dir: Path, archive_dir: Path, app_name: str, *, now: dt.datetime | None = None
) -> Path | None:
    """既存の配布パッケージをタイムスタンプ付きフォルダへ退避する（削除せず残す）。

    以前のパッケージと最新パッケージを比較調査できるようにするため、PyInstallerに
    既存出力先の削除を任せず、本スクリプト側で先にリネーム（`shutil.move`）で
    退避しておく。リネームはディレクトリエントリの付け替えのみで再帰的なファイル削除を
    伴わないため、OneDriveファイルオンデマンド配下でリパースポイント化された
    ディレクトリを`shutil.rmtree`で削除しようとして`WinError 5`になる問題
    （OPERATIONS.md参照）も併せて回避できる。

    戻り値: 退避先のパス。既存パッケージが無ければ何もせず`None`を返す。
    """
    if not output_dir.exists():
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or dt.datetime.now()).strftime("%Y%m%d_%H%M%S")
    destination = archive_dir / f"{app_name}_{timestamp}"
    shutil.move(str(output_dir), str(destination))
    return destination


def read_current_version(pyproject_path: Path) -> str:
    """`pyproject.toml`の`[project] version`を読み取る（配布バージョンの既定値・確認表示用）。"""
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def write_version(pyproject_path: Path, version: str) -> None:
    """`pyproject.toml`の`version`行のみを書き換える（他の内容・整形は保持する）。

    tomllibは読み取り専用（標準ライブラリにTOML書き込み機能が無い）ため、対象行を
    正規表現で置換する。`version = "..."`という1行のみを対象とし、それ以外の記述
    （コメント・依存関係一覧等）には触れない。
    """
    text = pyproject_path.read_text(encoding="utf-8")
    new_text, count = _VERSION_LINE_PATTERN.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise ValueError(f"pyproject.tomlのversion行が見つかりません: {pyproject_path}")
    pyproject_path.write_text(new_text, encoding="utf-8")


def resolve_version(current_version: str, *, prompt=input) -> str:
    """配布バージョンをユーザに明示的に入力させ、そのままリリースバージョンとして確定する。

    現在のバージョン（`pyproject.toml`の値）は参考表示のみで、既定値として自動採用は
    しない。空入力、および半角英数字・ドット・ハイフン・アンダースコア以外を含む入力は
    許可せず、有効な値が入力されるまで再度入力を求める（pyproject.tomlのTOML文字列・
    zipファイル名への埋め込み時の破損・パスずれを防ぐため）。

    戻り値: ユーザが入力した配布バージョン文字列。
    """
    while True:
        message = f"配布バージョンを入力してください（現在のバージョン: {current_version}）: "
        entered = prompt(message).strip()
        if not entered:
            print("  → バージョンが未入力です。空欄のままでは確定できません。")
            continue
        if not _VALID_VERSION_PATTERN.fullmatch(entered):
            print("  → バージョンに使用できる文字は半角英数字・ドット・ハイフン・")
            print("    アンダースコアのみです。")
            continue
        return entered


def run_tests() -> None:
    """バックエンド・フロントエンド双方のテストを実行する。1件でも失敗すればビルドを中止する。

    配布パッケージに不具合を含んだまま出荷しないための最終防波堤として、ビルドの
    一番最初に置く（バージョン入力より前。失敗する可能性のあるビルドでユーザに
    バージョンを入力させるのは手間の無駄なため）。

    フロントエンドは長らく対象外で、`npm test`（カバレッジ閾値100%）も型チェックも
    手動実行に頼っていた。バックエンドだけを通して出荷する状態は品質ゲートとして
    不完全なため、双方を必須にしている。

    テストファイルは pytest・vitest がそれぞれ既定の規則で探索するため、テストを追加しても
    ここへ登録する必要はない（追加漏れで実行されないことがない）。

    `--cov-fail-under=100` はここで明示的に渡す。CODING_RULES.md「テストカバレッジ」が
    掲げる100%を出荷時に機械的に強制するためで、`pyproject.toml` の addopts へは入れない
    （部分実行〈pytest tests/test_goal_service.py 等〉が常に閾値割れで失敗するため）。
    """
    print("[1/8] テストスイートを実行しています…")
    print("  → バックエンド (pytest + カバレッジ)")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--cov-fail-under=100"], cwd=BACKEND_DIR
    )
    if result.returncode != 0:
        print("  → バックエンドのテストが失敗しました。配布パッケージのビルドを中止します。")
        print("     上記のテスト結果を確認して修正した後、再度実行してください。")
        sys.exit(1)

    # npm は Windows ではシェル経由でないと解決できないため shell=True を使う
    # （build_frontend と同じ理由）。
    for label, command in (
        ("フロントエンド (型チェック)", ["npx", "tsc", "-b"]),
        ("フロントエンド (vitest + カバレッジ)", ["npm", "test"]),
    ):
        print(f"  → {label}")
        result = subprocess.run(command, cwd=FRONTEND_DIR, shell=True)
        if result.returncode != 0:
            print(f"  → {label} が失敗しました。配布パッケージのビルドを中止します。")
            sys.exit(1)


def generate_build_info(
    repo_root: Path, output_path: Path, *, now: dt.datetime | None = None
) -> Path:
    """アプリバージョン・使用ライブラリのスナップショットを`build_info.json`へ書き出す。

    ここで生成したファイルはPyInstallerの`--add-data`で配布パッケージへ同梱し、
    配布exe（frozen実行時）はこのファイルを読むだけにする
    （`app/services/system_info_service.py`のモジュールdocstring参照。frozen環境では
    `importlib.metadata`がdist-info情報を保持しない場合があるため、ビルド時＝
    依存関係が正しくインストールされたこの環境でのみライブ計算する）。

    バージョン確定（`resolve_version`/`write_version`）より後に呼ぶこと。
    `collect_build_info`は`pyproject.toml`から都度読み直すため、確定済みの新しい
    バージョンが正しく反映される。
    """
    built_at = (now or dt.datetime.now(dt.UTC)).isoformat()
    build_info = collect_build_info(repo_root, built_at=built_at)
    output_path.write_text(build_info_to_json(build_info), encoding="utf-8")
    return output_path


def build_frontend() -> None:
    print("[5/8] フロントエンドをビルドしています…")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True, shell=True)


def build_backend() -> None:
    print("[6/8] PyInstallerでバックエンドをパッケージ化しています…")
    add_data = [
        f"{FRONTEND_DIST_DIR}{os.pathsep}frontend_dist",
        f"{BACKEND_DIR / 'alembic.ini'}{os.pathsep}.",
        f"{BACKEND_DIR / 'alembic'}{os.pathsep}alembic",
        f"{BUILD_INFO_PATH}{os.pathsep}.",
    ]
    args = [sys.executable, "-m", "PyInstaller", "--name", APP_NAME, "--noconfirm"]
    for entry in add_data:
        args += ["--add-data", entry]
    args.append(str(BACKEND_DIR / "app" / "main.py"))
    subprocess.run(args, cwd=BACKEND_DIR, check=True)


def copy_user_manual(manual_path: Path, output_dir: Path) -> Path | None:
    """ユーザ手順書PDFを配布パッケージのフォルダ直下へ複製する。

    配布先ではリポジトリを参照できないため、zipを展開しただけで手順書を開けるよう
    パッケージへ同梱する。PyInstallerの`--add-data`（`build_backend`）ではなく単純な
    ファイルコピーにしているのは、`--add-data`で同梱したファイルはexe内へ埋め込まれ、
    利用者がエクスプローラから直接開けなくなるため（手順書は利用者がダブルクリックして
    読む用途であり、アプリ実行時に読み込むリソースではない）。

    手順書が見つからない場合は警告を表示して同梱のみを飛ばす（アプリの動作自体には
    影響しないため、ここでビルドを中止はしない）。

    戻り値: 複製先のパス。手順書が存在しなければ`None`。
    """
    if not manual_path.exists():
        print(f"  → 警告: ユーザ手順書が見つからないため同梱をスキップします: {manual_path}")
        return None
    destination = output_dir / manual_path.name
    shutil.copy(manual_path, destination)
    return destination


def assemble_launcher() -> None:
    print("[7/8] 起動用batファイル・ユーザ手順書を配置しています…")
    launcher_dst = OUTPUT_DIR / f"{APP_NAME}.bat"
    shutil.copy(LAUNCHER_TEMPLATE_PATH, launcher_dst)
    copied_manual = copy_user_manual(USER_MANUAL_PATH, OUTPUT_DIR)
    if copied_manual is not None:
        print(f"  → ユーザ手順書を同梱しました: {copied_manual.name}")
    print(f"完了: {OUTPUT_DIR}")


def distribution_zip_filename(app_name: str, version: str) -> str:
    """配布用zipのファイル名を組み立てる（`create_distribution_zip`・
    `publish_release.py`の双方から利用し、命名規則を1箇所に集約する。
    CLAUDE.md DRYの原則）。"""
    return f"{app_name}-v{version}.zip"


def build_commit_filename(app_name: str, version: str) -> str:
    """ビルド元コミットの記録ファイル名（配布zipと対になる名前にする）。

    命名を`distribution_zip_filename`から導出し、zipとの対応を1箇所で決める
    （CLAUDE.md DRYの原則）。
    """
    return distribution_zip_filename(app_name, version).removesuffix(".zip") + BUILD_COMMIT_SUFFIX


def read_git_commit(repo_root: Path) -> str | None:
    """`HEAD`のコミットSHAを返す（gitが使えない場合は`None`）。"""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def has_uncommitted_changes(repo_root: Path) -> bool | None:
    """作業ツリーに未コミットの変更があるかを返す（gitが使えない場合は`None`）。

    **バージョン確定（`write_version`）より前に呼ぶこと。** 本スクリプトはビルドの
    過程で`pyproject.toml`のバージョン行を書き換えるため、確定後に判定すると常に
    「変更あり」になってしまう。
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def generate_build_commit(
    output_path: Path, version: str, commit: str | None, *, dirty: bool | None
) -> Path:
    """配布zipと対になる、ビルド元コミットの記録を書き出す。

    `publish_release.py`がこれを読み、`ensure_release_tag`で**配布物のコミットへタグを
    付ける**。記録が無いとタグは公開時点の既定ブランチ先端に付くため、ビルドと公開の間に
    `main`が進むと配布物と異なるコミットへタグが付く（2026-09-11に`ver1.0.0`・`ver1.2.0`
    で実際に発生。OPERATIONS.md 7.4参照）。
    """
    record = {"version": version, "commit": commit, "dirty": dirty}
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def create_distribution_zip(output_dir: Path, dist_dir: Path, app_name: str, version: str) -> Path:
    """ビルド済みパッケージフォルダをzip化し、配布時のコピー手間を省く。

    既存パッケージのアーカイブ退避（`archive_previous_package`）はビルド前に
    `output_dir`（例: `backend/dist/Michinari/`）をリネーム退避する処理であり、
    本関数はビルド後に生成された最新の`output_dir`のみをzip化するため、退避処理
    とは対象・実行順序の両面で独立している。zip出力先（`dist_dir`直下）は退避先
    （`dist_dir/_archive/`）と重ならないため、退避処理が誤って新しいzipを巻き込む
    ことも、zip化が退避済みの旧パッケージを巻き込むこともない。

    ファイル名に確定済みバージョンを含める（例: `Michinari-v0.2.0.zip`）ため、
    GitHub Releasesへアップロードする際にタグ・リリース名と対応付けやすい。

    戻り値: 生成したzipファイルのパス。同一バージョンで再ビルドした場合のみ
    上書きされる（バージョンが異なれば別ファイルとして残る）。
    """
    zip_filename = distribution_zip_filename(app_name, version)
    archive_path = shutil.make_archive(
        base_name=str(dist_dir / zip_filename.removesuffix(".zip")),
        format="zip",
        root_dir=str(dist_dir),
        base_dir=app_name,
    )
    return Path(archive_path)


def main() -> None:
    run_tests()

    print("[2/8] 配布バージョンを確認しています…")
    # バージョン確定（write_version）でpyproject.tomlが書き換わる前に、作業ツリーの
    # 状態とHEADを記録する（`has_uncommitted_changes`のdocstring参照）。
    dirty = has_uncommitted_changes(REPO_ROOT)
    commit = read_git_commit(REPO_ROOT)
    current_version = read_current_version(PYPROJECT_PATH)
    version = resolve_version(current_version)
    if version != current_version:
        write_version(PYPROJECT_PATH, version)
        print(f"  → pyproject.tomlのバージョンを更新しました: {current_version} → {version}")
    print(f"  → バージョン {version} でビルドします")

    print("[3/8] 既存パッケージを確認しています…")
    archived_to = archive_previous_package(OUTPUT_DIR, ARCHIVE_DIR, APP_NAME)
    if archived_to:
        print(f"  → 既存パッケージを退避しました: {archived_to}")
    else:
        print("  → 既存パッケージはありません")

    print("[4/8] ビルド情報（バージョン・使用ライブラリ）を生成しています…")
    generate_build_info(REPO_ROOT, BUILD_INFO_PATH)

    build_frontend()
    build_backend()
    assemble_launcher()

    print("[8/8] 配布用zipを作成しています…")
    zip_path = create_distribution_zip(OUTPUT_DIR, DIST_DIR, APP_NAME, version)
    commit_path = generate_build_commit(
        DIST_DIR / build_commit_filename(APP_NAME, version), version, commit, dirty=dirty
    )
    if dirty:
        print("  → 警告: 未コミットの変更がある状態でビルドしました。")
        print("     この配布物に対応するコミットが存在しないため、publish_release.py は")
        print(
            "     公開を中止します。変更をコミットして main へマージしてから再ビルドしてください。"
        )
    print(f"完了: {zip_path}")
    print(f"      {commit_path.name}（ビルド元コミットの記録）")


if __name__ == "__main__":
    main()
