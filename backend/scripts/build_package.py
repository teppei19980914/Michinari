"""配布パッケージのビルドスクリプト（PyInstallerでの単一実行ファイル化、OPERATIONS.md参照）。

実行順序: テストスイートの実行（1件でも失敗すればここでビルドを中止する）→
配布バージョンをユーザ入力で確定（`backend/pyproject.toml`へ反映）→
既存配布物（zip・ビルド元コミットの記録）のアーカイブ退避と旧ビルド出力の削除 →
ビルド情報（バージョン・使用ライブラリ）の生成 →
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
#: `_archive/`へ退避する既存配布物の拡張子。配布zipと、それと対になるビルド元コミットの
#: 記録（`BUILD_COMMIT_SUFFIX`）の2種類のみを対象とし、ビルド出力フォルダは含めない。
ARCHIVED_DISTRIBUTION_SUFFIXES = (".zip", ".json")
#: 旧パッケージフォルダを削除する前に付け替える一時名の接頭辞（`discard_previous_package`）。
PREVIOUS_PACKAGE_PREFIX = "_previous_"
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


def archive_previous_distributions(dist_dir: Path, archive_dir: Path) -> list[Path]:
    """`dist/`直下の既存配布物（zipとビルド元コミットの記録）を`_archive/`へ退避する。

    退避対象は`ARCHIVED_DISTRIBUTION_SUFFIXES`の拡張子を持つ**ファイルのみ**で、
    ビルド出力フォルダ（`dist/Michinari/`）は対象にしない。以前はフォルダごと
    `_archive/`へ退避していたが、1回のビルドで数十〜100MB超になるフォルダが
    ビルドのたびに積み上がり、`dist/`の容量が増大していたためである
    （OPERATIONS.md「配布パッケージのビルド」参照）。zipには同じ内容が圧縮された形で
    残るため、旧版を調べたいときはzipを展開すればよい。

    退避先に同名ファイルがある場合（同一バージョンで再ビルドした場合）は上書きする。

    戻り値: 退避したファイルの退避先パス一覧（ファイル名昇順）。対象が無ければ空リスト。
    """
    if not dist_dir.exists():
        return []
    sources = sorted(
        path
        for path in dist_dir.iterdir()
        if path.is_file() and path.suffix in ARCHIVED_DISTRIBUTION_SUFFIXES
    )
    if not sources:
        return []
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for source in sources:
        destination = archive_dir / source.name
        destination.unlink(missing_ok=True)
        shutil.move(str(source), str(destination))
        moved.append(destination)
    return moved


def discard_previous_package(output_dir: Path, *, now: dt.datetime | None = None) -> Path | None:
    """既存のビルド出力フォルダを削除し、同じ場所へ新しいバージョンをビルドできるようにする。

    削除は「同階層の一時名へリネーム → その一時フォルダを再帰削除」の2段階で行う。
    リネームはディレクトリエントリの付け替えのみで完了するため出力先を確実に空けられ、
    OneDriveファイルオンデマンド配下で再帰削除が`WinError 5 アクセスが拒否されました`に
    なる事象（OPERATIONS.md参照）が起きても、ビルド自体は中断せずに進められる。
    削除できなかった一時フォルダは警告を表示して残す（手動削除できるようにする）。

    PyInstallerの`--noconfirm`任せにせず本スクリプト側で先に空けるのも同じ理由である。

    戻り値: 削除に失敗して残った一時フォルダのパス。削除できた場合・既存フォルダが
    無い場合は`None`。
    """
    if not output_dir.exists():
        return None
    timestamp = (now or dt.datetime.now()).strftime("%Y%m%d_%H%M%S")
    staging_dir = output_dir.parent / f"{PREVIOUS_PACKAGE_PREFIX}{output_dir.name}_{timestamp}"
    shutil.move(str(output_dir), str(staging_dir))
    try:
        shutil.rmtree(staging_dir)
    except OSError as error:
        print(f"  → 警告: 旧パッケージを削除できませんでした: {staging_dir} ({error})")
        print("     ビルドは継続します。不要であれば手動で削除してください。")
        return staging_dir
    return None


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


def run_smoke() -> None:
    """リリース前スモーク（起動確認・既存DBの移行確認）を行う。問題があればビルドを中止する。

    テストスイートでは原理的に確認できない2点（アプリが実際に起動して応答するか、既存の
    利用者データベースが移行できるか）を、出荷前に機械的に確かめる（OPERATIONS.md
    「リリース前スモークテスト」参照）。

    `release.bat` の手順を増やさず `run_tests` の直後に置くのは、別手順にすると実行を
    忘れうるためである。判定と表示は `release_smoke.collect_problems` に集約しており、
    コマンドラインから単体で流したときと同じ確認を行う。

    配布パッケージ（exe）の起動確認はここには含めない。配布物はフロントエンドを同梱して
    おり起動するとブラウザが開くため、リリース中に割り込ませない
    （`release_smoke.py --package` で必要なときに実行する）。
    """
    # release_smoke は配布物の命名・配置を本モジュールから取り込むため、モジュール先頭で
    # 取り込むと循環参照になる。呼び出し時にだけ解決する。
    import release_smoke

    print("  → リリース前スモーク (起動確認・既存DBの移行確認)")
    problems = release_smoke.collect_problems()
    if problems:
        print("  → スモークテストが失敗しました。配布パッケージのビルドを中止します。")
        for problem in problems:
            print(f"     - {problem}")
        sys.exit(1)


def run_tests() -> None:
    """バックエンド・フロントエンド双方のテストとリリース前スモークを実行する。
    1件でも失敗すればビルドを中止する。

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

    run_smoke()


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

    既存配布物のアーカイブ退避（`archive_previous_distributions`）はビルド前に
    `dist_dir`直下の旧zip・旧記録を`dist_dir/_archive/`へ移す処理であり、本関数は
    ビルド後に生成された最新の`output_dir`（例: `backend/dist/Michinari/`）のみを
    zip化するため、退避処理とは対象・実行順序の両面で独立している。zip化の対象は
    `base_dir=app_name`に限られるため、`_archive/`や削除しきれず残った旧パッケージの
    一時フォルダ（`PREVIOUS_PACKAGE_PREFIX`）を巻き込むことはない。

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

    print("[3/8] 既存パッケージを整理しています…")
    archived = archive_previous_distributions(DIST_DIR, ARCHIVE_DIR)
    if archived:
        print(f"  → 既存の配布物 {len(archived)} 件を退避しました: {ARCHIVE_DIR}")
    else:
        print("  → 退避する既存の配布物はありません")
    discard_previous_package(OUTPUT_DIR)

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
