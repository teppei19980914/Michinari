"""配布パッケージビルドスクリプトのうち、実行中プロセス確認・ビルドコミット記録・
PyInstaller引数・サードパーティライセンス・リリース前スモークのテスト
（scripts/build_package.py参照）。既存配布物の退避・破棄・zip化・バージョン確定の
テストはtest_build_package_archive.py・_package.py・_version.pyを参照（実装フェーズ
分割計画書S02、test_build_package.pyからの分割。決定事項S7）。
"""

import json
import os
import subprocess
from pathlib import Path

import build_package
import collect_licenses
import pytest
from build_package import (
    build_commit_filename,
    ensure_app_not_running,
    generate_build_commit,
    has_uncommitted_changes,
    is_app_running,
    read_git_commit,
    run_smoke,
)

from app.constants.bundle import (
    ALEMBIC_INI_FILE_NAME,
    ASSETS_DIR_NAME,
    EXAM_TEMPLATES_DIR_NAME,
    FRONTEND_DIST_DIR_NAME,
    LOCALES_DIR_NAME,
)


def test_is_app_running_returns_true_when_tasklist_lists_the_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`tasklist`の出力に実行ファイル名が含まれていれば実行中と判定すること。"""

    def fake_run(args, **kwargs):
        assert args[:2] == ["tasklist", "/FI"]
        return subprocess.CompletedProcess(
            args, 0, stdout="Michinari.exe                16732 Console  1  73,708 K\n", stderr=""
        )

    monkeypatch.setattr(build_package.subprocess, "run", fake_run)

    assert is_app_running("Michinari.exe") is True


def test_is_app_running_returns_false_when_tasklist_finds_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """該当プロセスが無いと`tasklist`は「一致するタスクはありません」のみ返すこと。"""

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, stdout="INFO: 条件に指定されたタスクは実行されていません。\n", stderr=""
        )

    monkeypatch.setattr(build_package.subprocess, "run", fake_run)

    assert is_app_running("Michinari.exe") is False


def test_ensure_app_not_running_raises_when_the_app_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配布パッケージが実行中のままだと、ロックで後続のビルド手順が失敗するため
    早期にわかりやすいエラーで止めること（2026-09-26、`discard_previous_package`の
    再試行修正後もPyInstaller自身のクリーンアップが同じロックで失敗した事象への対応）。
    """
    monkeypatch.setattr(build_package, "is_app_running", lambda exe_name=None: True)

    with pytest.raises(SystemExit, match="Michinari.exe が実行中です"):
        ensure_app_not_running("Michinari.exe")


def test_ensure_app_not_running_passes_when_the_app_is_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_package, "is_app_running", lambda exe_name=None: False)

    ensure_app_not_running("Michinari.exe")


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_build_commit_filename_pairs_with_the_distribution_zip() -> None:
    """記録ファイル名が配布zipと対になること（publish_release.pyが同じ名前で探す）。"""
    assert build_commit_filename("Michinari", "1.2.3") == "Michinari-v1.2.3.commit.json"


def test_read_git_commit_returns_head_sha(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, "abc1234\n"),
    )

    assert read_git_commit(tmp_path) == "abc1234"


def test_read_git_commit_returns_none_outside_a_git_repository(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(128)
    )

    assert read_git_commit(tmp_path) is None


def test_has_uncommitted_changes_detects_a_dirty_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, " M backend/pyproject.toml\n"),
    )

    assert has_uncommitted_changes(tmp_path) is True


def test_has_uncommitted_changes_is_false_for_a_clean_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, "")
    )

    assert has_uncommitted_changes(tmp_path) is False


def test_has_uncommitted_changes_returns_none_outside_a_git_repository(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(128)
    )

    assert has_uncommitted_changes(tmp_path) is None


def test_generate_build_commit_records_version_commit_and_dirty_flag(tmp_path: Path) -> None:
    output_path = tmp_path / "Michinari-v1.2.3.commit.json"

    generate_build_commit(output_path, "1.2.3", "abc1234", dirty=False)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "version": "1.2.3",
        "commit": "abc1234",
        "dirty": False,
    }


def test_generate_build_commit_keeps_dirty_builds_identifiable(tmp_path: Path) -> None:
    """未コミットの木からのビルドを記録に残し、publish_release.pyが公開を止められること。"""
    output_path = tmp_path / "Michinari-v1.2.3.commit.json"

    generate_build_commit(output_path, "1.2.3", "abc1234", dirty=True)

    assert json.loads(output_path.read_text(encoding="utf-8"))["dirty"] is True


class TestRunSmoke:
    """リリースゲートに組み込んだスモークが、問題を見つけたらビルドを止めることを確かめる。

    実際の起動・移行確認は release_smoke 側のテストが担うため、ここでは
    「問題があれば中止し、無ければ素通しする」という接続部分だけを見る。
    """

    def test_passes_through_when_there_is_no_problem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("release_smoke.collect_problems", lambda: [])

        run_smoke()  # 例外もSystemExitも起きないこと

    def test_aborts_the_build_when_a_problem_is_found(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("release_smoke.collect_problems", lambda: ["goal: 5 行 → 4 行"])

        with pytest.raises(SystemExit) as excinfo:
            run_smoke()

        assert excinfo.value.code == 1
        assert "goal: 5 行 → 4 行" in capsys.readouterr().out


class TestPyInstallerArgs:
    """PyInstallerへ渡す引数の検証（Phase37）。

    実際のビルドはCI環境依存が大きいため対象外とし、「配布物が正しく組み立つための
    指定が欠けていないか」を引数の内容で確かめる。ここが崩れると、開発環境では動くのに
    配布物だけが壊れる（同梱漏れは実行時まで表面化しない）。
    """

    @staticmethod
    def _args() -> list[str]:
        return build_package.pyinstaller_args()

    def test_hides_the_console_window(self) -> None:
        """黒いコンソールを出さないこと（Phase37の主目的）。"""
        assert "--noconsole" in self._args()

    def test_uses_the_application_icon(self) -> None:
        args = self._args()

        assert args[args.index("--icon") + 1] == str(build_package.ICON_SOURCE_PATH)
        assert build_package.ICON_SOURCE_PATH.is_file()

    def test_bundles_every_supported_locale_file_where_the_app_looks_for_it(self) -> None:
        """トレイ・通知の文言が、対応言語の全てで配布物でも解決できること
        （日英i18n対応、2026-10。片方だけ同梱すると配布物でのみその言語が
        キー文字列表示になる不具合になるため、両方を確認する）。"""
        args = self._args()

        assert len(build_package.LOCALE_SOURCE_PATHS) == len(build_package.SUPPORTED_LOCALES)
        for locale_path in build_package.LOCALE_SOURCE_PATHS:
            assert f"{locale_path}{os.pathsep}{LOCALES_DIR_NAME}" in args
            assert locale_path.is_file()

    def test_bundles_the_icon_directory_where_the_app_looks_for_it(self) -> None:
        """トレイ・通知がアイコンを読み込めること。"""
        expected = f"{build_package.ICON_SOURCE_DIR}{os.pathsep}{ASSETS_DIR_NAME}"

        assert expected in self._args()

    def test_bundles_the_exam_templates_where_the_app_looks_for_them(self) -> None:
        """資格テンプレートJSONが配布物でも`GET /exam-templates`から読めること（Phase38）。"""
        expected = f"{build_package.EXAM_TEMPLATES_SOURCE_DIR}{os.pathsep}{EXAM_TEMPLATES_DIR_NAME}"

        assert expected in self._args()
        assert build_package.EXAM_TEMPLATES_SOURCE_DIR.is_dir()

    def test_keeps_bundling_the_frontend_and_migrations(self) -> None:
        """従来からの同梱物が落ちていないこと（Phase37の変更の巻き添えを防ぐ）。"""
        args = self._args()

        assert any(entry.endswith(f"{os.pathsep}{FRONTEND_DIST_DIR_NAME}") for entry in args)
        assert any(entry.endswith(f"{os.pathsep}alembic") for entry in args)
        assert any(ALEMBIC_INI_FILE_NAME in entry for entry in args)

    def test_builds_the_application_entry_point(self) -> None:
        assert self._args()[-1].endswith("main.py")


class TestThirdPartyLicenses:
    """同梱ライブラリのライセンス義務（Phase37）。

    本アプリは公開リポジトリのGitHub Releasesで配布するため、義務は全世界への頒布として
    発生する。とりわけ `pystray` は LGPL-3.0 であり、表記に加えて「利用者が改変版へ
    差し替えられること」までが求められる。ここが崩れたまま配布すると気付けないため、
    ビルド引数と生成物の両方を検証する。
    """

    def test_bundles_the_notices_and_license_texts(self, tmp_path: Path) -> None:
        notices = collect_licenses.collect(tmp_path)

        assert notices.name == collect_licenses.NOTICES_FILE_NAME
        body = notices.read_text(encoding="utf-8")
        for library in collect_licenses.BUNDLED_LIBRARIES:
            assert library.distribution in body
            assert library.license_name in body

    def test_copies_every_declared_license_file(self, tmp_path: Path) -> None:
        collect_licenses.collect(tmp_path)

        licenses_dir = tmp_path / collect_licenses.LICENSES_DIR_NAME
        copied = {path.name for path in licenses_dir.iterdir()}
        for library in collect_licenses.BUNDLED_LIBRARIES:
            for relative in library.license_files:
                assert f"{library.distribution}-{Path(relative).name}" in copied

    def test_license_texts_are_not_empty(self, tmp_path: Path) -> None:
        collect_licenses.collect(tmp_path)

        for path in (tmp_path / collect_licenses.LICENSES_DIR_NAME).iterdir():
            assert path.stat().st_size > 0

    def test_declares_pystray_as_lgpl(self) -> None:
        """LGPLのライブラリが表記対象から外れていないこと。"""
        by_name = {lib.distribution: lib for lib in collect_licenses.BUNDLED_LIBRARIES}

        assert "LGPL" in by_name["pystray"].license_name

    def test_fails_loudly_when_a_license_file_is_missing(self, tmp_path: Path) -> None:
        """表記漏れのまま配布しないこと（警告で済ませず失敗させる）。"""
        broken = (collect_licenses.BundledLibrary("pystray", "LGPL-3.0", ("NOT_A_REAL_FILE",)),)

        with pytest.raises(FileNotFoundError):
            collect_licenses.collect(tmp_path, broken)

    def test_pystray_is_not_embedded_in_the_executable(self) -> None:
        """LGPL-3.0 第4条(d): 利用者が改変版へ差し替えられる形で配置すること。

        exeへ埋め込むと差し替えられないため、`--exclude-module` で除外し、
        素のファイルとして同梱する。
        """
        args = build_package.pyinstaller_args()

        assert "--exclude-module" in args
        assert args[args.index("--exclude-module") + 1] == build_package.LGPL_MODULE_NAME
        assert any(
            entry.endswith(f"{os.pathsep}{build_package.LGPL_MODULE_NAME}") for entry in args
        )

    def test_bundles_help_content_where_the_runtime_reads_it(self) -> None:
        """ヘルプAIアシスタントの本文（Phase43）を同梱する。実行時の読み込み先と対になること。

        `help_content.py` は `app/content/help_content.json` を読む。同梱先がずれると、
        配布版だけヘルプに答えられなくなるため、同梱の指定を固定する。
        """
        args = build_package.pyinstaller_args()

        expected = (
            f"{build_package.HELP_CONTENT_SOURCE_PATH}{os.pathsep}"
            f"{build_package.HELP_CONTENT_DIR_NAME}"
        )
        assert expected in args
        assert build_package.HELP_CONTENT_SOURCE_PATH.is_file()

    def test_keeps_the_dependency_that_only_pystray_pulls_in(self) -> None:
        """除外した pystray からしか辿られない依存を明示すること（無いと起動時に落ちる）。"""
        args = build_package.pyinstaller_args()

        assert args[args.index("--hidden-import") + 1] == "six"

    def test_lgpl_module_source_dir_points_at_the_installed_package(self) -> None:
        source_dir = build_package.lgpl_module_source_dir()

        assert source_dir.is_dir()
        assert (source_dir / "__init__.py").is_file()


def test_run_tests_writes_coverage_data_outside_backend_dir(monkeypatch) -> None:
    """release の pytest のカバレッジ出力を backend/ の外へ分け、Stop Hook 等の並行実行と
    データファイルを共有しないことを固定する（2026-10-05 release.bat の PermissionError）。"""
    calls: list[dict] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(build_package.subprocess, "run", fake_run)

    build_package.run_tests()

    pytest_call = calls[0]
    assert "pytest" in pytest_call["args"]
    coverage_file = Path(pytest_call["env"]["COVERAGE_FILE"])
    assert coverage_file.name == ".coverage"
    assert build_package.BACKEND_DIR not in coverage_file.parents
