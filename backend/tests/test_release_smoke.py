"""リリース前スモークテスト（scripts/release_smoke.py）のロジックのテスト。

実プロセスの起動（`start_app`/`stop_app`）と実HTTP通信（`fetch_status`）はOS・ネットワーク
依存が大きいため対象外とし、それ以外の判定ロジックを検証する（test_build_package.py が
PyInstaller本体を対象外としているのと同じ方針）。

スモークテスト自身が壊れていると「問題がないから通った」のか「検知できずに通った」のか
区別できないため、**問題を検知する側の経路**を重点的に固定する。
"""

import sqlite3
from pathlib import Path

import pytest
from release_smoke import (
    _run_package_step,
    build_child_env,
    check_endpoints,
    collect_problems,
    extract_package,
    find_latest_package,
    find_shrunk_tables,
    main,
    run_startup_smoke,
    table_row_counts,
    verify_migration,
    wait_for_health,
)

BASE_URL = "http://127.0.0.1:65000"


def make_fetch(responses: dict[str, int | Exception]):
    """URL→ステータス（または送出する例外）の対応から`Fetch`を作る。"""

    def fetch(url: str) -> int:
        result = responses[url]
        if isinstance(result, Exception):
            raise result
        return result

    return fetch


class TestBuildChildEnv:
    def test_points_the_database_url_at_the_given_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "smoke.db"

        env = build_child_env(db_path, {"EXISTING": "kept"})

        assert env["MICHINARI_DATABASE_URL"] == f"sqlite:///{db_path.as_posix()}"
        assert env["EXISTING"] == "kept"

    def test_does_not_mutate_the_given_environment(self, tmp_path: Path) -> None:
        base = {"EXISTING": "kept"}

        build_child_env(tmp_path / "smoke.db", base)

        assert "MICHINARI_DATABASE_URL" not in base


class TestWaitForHealth:
    def test_returns_true_as_soon_as_health_answers(self) -> None:
        fetch = make_fetch({f"{BASE_URL}/health": 200})

        assert wait_for_health(fetch, BASE_URL, now=lambda: 0.0) is True

    def test_keeps_waiting_while_the_connection_is_refused(self) -> None:
        # 起動直後は接続を拒否されるのが正常。例外で諦めてはいけない。
        attempts = {"count": 0}

        def fetch(_url: str) -> int:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ConnectionRefusedError("not yet")
            return 200

        assert wait_for_health(fetch, BASE_URL, sleep=lambda _s: None, now=lambda: 0.0) is True
        assert attempts["count"] == 3

    def test_keeps_waiting_while_health_is_not_ready(self) -> None:
        statuses = iter([503, 503, 200])

        assert (
            wait_for_health(
                lambda _url: next(statuses), BASE_URL, sleep=lambda _s: None, now=lambda: 0.0
            )
            is True
        )

    def test_gives_up_when_the_deadline_passes(self) -> None:
        clock = iter([0.0, 0.0, 99.0])

        result = wait_for_health(
            make_fetch({f"{BASE_URL}/health": ConnectionRefusedError("never")}),
            BASE_URL,
            timeout_seconds=1.0,
            sleep=lambda _s: None,
            now=lambda: next(clock),
        )

        assert result is False


class TestCheckEndpoints:
    def test_reports_nothing_when_every_endpoint_answers_200(self) -> None:
        fetch = make_fetch({f"{BASE_URL}/a": 200, f"{BASE_URL}/b": 200})

        assert check_endpoints(fetch, BASE_URL, ["/a", "/b"]) == []

    def test_reports_a_non_200_status(self) -> None:
        fetch = make_fetch({f"{BASE_URL}/a": 200, f"{BASE_URL}/b": 500})

        failures = check_endpoints(fetch, BASE_URL, ["/a", "/b"])

        assert len(failures) == 1
        assert "/b" in failures[0] and "500" in failures[0]

    def test_reports_a_connection_failure(self) -> None:
        fetch = make_fetch({f"{BASE_URL}/a": ConnectionRefusedError("down")})

        failures = check_endpoints(fetch, BASE_URL, ["/a"])

        assert len(failures) == 1
        assert "/a" in failures[0]

    def test_checks_every_endpoint_even_after_one_fails(self) -> None:
        fetch = make_fetch({f"{BASE_URL}/a": 500, f"{BASE_URL}/b": 500})

        assert len(check_endpoints(fetch, BASE_URL, ["/a", "/b"])) == 2


class TestTableRowCounts:
    def test_counts_rows_and_ignores_bookkeeping_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sample.db"
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE goal (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO goal (id) VALUES (1), (2)")
        connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
        connection.execute("INSERT INTO alembic_version VALUES ('abc')")
        connection.commit()
        connection.close()

        counts = table_row_counts(db_path)

        assert counts == {"goal": 2}


class TestFindShrunkTables:
    def test_reports_nothing_when_no_row_was_lost(self) -> None:
        assert find_shrunk_tables({"goal": 2}, {"goal": 2}) == []

    def test_allows_rows_and_tables_to_be_added(self) -> None:
        # マイグレーションで行やテーブルが増えるのは正常。
        assert find_shrunk_tables({"goal": 2}, {"goal": 3, "book": 1}) == []

    def test_reports_a_table_that_lost_rows(self) -> None:
        failures = find_shrunk_tables({"goal": 5}, {"goal": 4})

        assert len(failures) == 1
        assert "goal" in failures[0]

    def test_reports_a_table_that_disappeared(self) -> None:
        failures = find_shrunk_tables({"goal": 5}, {})

        assert len(failures) == 1
        assert "goal" in failures[0]


class TestVerifyMigration:
    """実データベースを壊さないことと、既存データを保ったまま適用できることを確かめる。"""

    def _make_legacy_db(self, db_path: Path) -> None:
        """初期スキーマのまま止まっている既存DBを模す（`alembic_version`を古い版に固定）。"""
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE legacy_note (id INTEGER PRIMARY KEY, body TEXT)")
        connection.execute("INSERT INTO legacy_note (id, body) VALUES (1, 'keep me')")
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        # head を指定して「適用すべきものがない」状態にする（本テストの狙いは移行の中身ではなく、
        # 複製に対して動くこと・元のDBを触らないこと・環境変数を戻すことの確認のため）。
        connection.execute("INSERT INTO alembic_version VALUES ('a9e3c5b71d64')")
        connection.commit()
        connection.close()

    def test_keeps_the_source_database_untouched(self, tmp_path: Path) -> None:
        source = tmp_path / "michinari.db"
        self._make_legacy_db(source)
        before = source.read_bytes()
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        verify_migration(source, work_dir)

        # 利用者のデータベースは読み取りのみ。書き換えたら移行確認そのものが事故になる。
        assert source.read_bytes() == before

    def test_reports_nothing_when_the_rows_survive(self, tmp_path: Path) -> None:
        source = tmp_path / "michinari.db"
        self._make_legacy_db(source)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        assert verify_migration(source, work_dir) == []

    def test_restores_the_database_url_afterwards(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 環境変数を戻し損ねると、以後のテストが一時DBを見続けてしまう。
        monkeypatch.setenv("MICHINARI_DATABASE_URL", "sqlite:///original.db")
        source = tmp_path / "michinari.db"
        self._make_legacy_db(source)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        verify_migration(source, work_dir)

        import os

        assert os.environ["MICHINARI_DATABASE_URL"] == "sqlite:///original.db"


class TestRunStartupSmoke:
    def test_reports_a_failure_when_the_app_never_answers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        started: list[str] = []

        class DummyProcess:
            stdout = None

            def poll(self) -> int:
                return 0

        monkeypatch.setattr(
            "release_smoke.start_app",
            lambda _port, _db: (started.append("started"), DummyProcess())[1],
        )
        monkeypatch.setattr("release_smoke.wait_for_health", lambda *_a, **_k: False)

        failures = run_startup_smoke(fetch=lambda _url: 200)

        assert started == ["started"]
        assert len(failures) == 1
        assert "起動しませんでした" in failures[0]

    def test_checks_the_endpoints_once_the_app_is_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stopped: list[str] = []

        class DummyProcess:
            stdout = None

            def poll(self) -> int:
                return 0

        monkeypatch.setattr("release_smoke.start_app", lambda _port, _db: DummyProcess())
        monkeypatch.setattr("release_smoke.wait_for_health", lambda *_a, **_k: True)
        monkeypatch.setattr("release_smoke.stop_app", lambda _p: stopped.append("stopped"))

        failures = run_startup_smoke(fetch=lambda _url: 500, endpoints=["/health"])

        assert len(failures) == 1
        # 検証の成否にかかわらず、起動したプロセスは必ず止める。
        assert stopped == ["stopped"]


class TestMain:
    def test_succeeds_when_both_checks_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("release_smoke.run_startup_smoke", lambda: [])
        monkeypatch.setattr("release_smoke.verify_migration", lambda _s, _w: [])
        database = tmp_path / "michinari.db"
        database.write_bytes(b"")

        assert main(["--database", str(database)]) == 0
        assert "全て通過" in capsys.readouterr().out

    def test_fails_when_the_startup_smoke_finds_a_problem(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("release_smoke.run_startup_smoke", lambda: ["/health: HTTP 500"])

        assert main(["--skip-migration"]) == 1
        assert "/health: HTTP 500" in capsys.readouterr().out

    def test_fails_when_the_migration_loses_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("release_smoke.verify_migration", lambda _s, _w: ["goal: 5 行 → 4 行"])
        database = tmp_path / "michinari.db"
        database.write_bytes(b"")

        assert main(["--skip-startup", "--database", str(database)]) == 1
        assert "goal: 5 行 → 4 行" in capsys.readouterr().out

    def test_skips_the_migration_check_when_there_is_no_database_yet(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 新規環境では既存DBが無いのが正常であり、失敗にしてはいけない。
        missing = tmp_path / "absent.db"

        assert main(["--skip-startup", "--database", str(missing)]) == 0
        assert "省略" in capsys.readouterr().out

    def test_can_skip_both_checks(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--skip-startup", "--skip-migration"]) == 0
        assert "全て通過" in capsys.readouterr().out


def _write_zip(zip_path: Path, names: list[str]) -> None:
    """指定した相対パスを持つだけのzipを作る（中身は検証に使わないため空でよい）。"""
    import zipfile

    with zipfile.ZipFile(zip_path, "w") as archive:
        for name in names:
            archive.writestr(name, "")


class TestFindLatestPackage:
    def test_returns_none_when_the_directory_does_not_exist(self, tmp_path: Path) -> None:
        assert find_latest_package(tmp_path / "absent") is None

    def test_returns_none_when_there_is_no_package(self, tmp_path: Path) -> None:
        assert find_latest_package(tmp_path) is None

    def test_picks_the_most_recently_built_package(self, tmp_path: Path) -> None:
        import os

        older = tmp_path / "Michinari-v1.0.0.zip"
        newer = tmp_path / "Michinari-v1.2.2.zip"
        _write_zip(older, ["Michinari/Michinari.exe"])
        _write_zip(newer, ["Michinari/Michinari.exe"])
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))

        assert find_latest_package(tmp_path) == newer

    def test_ignores_zips_bundled_inside_the_package(self, tmp_path: Path) -> None:
        # dist/Michinari/_internal/base_library.zip のような同梱物を拾ってはいけない。
        nested = tmp_path / "Michinari" / "_internal"
        nested.mkdir(parents=True)
        _write_zip(nested / "Michinari-v9.9.9.zip", ["dummy"])

        assert find_latest_package(tmp_path) is None


class TestExtractPackage:
    def test_returns_the_path_of_the_executable(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "Michinari-v1.0.0.zip"
        _write_zip(zip_path, ["Michinari/Michinari.exe", "Michinari/readme.txt"])

        exe_path = extract_package(zip_path, tmp_path / "out")

        assert exe_path is not None
        assert exe_path.name == "Michinari.exe"
        assert exe_path.is_file()

    def test_returns_none_when_the_executable_is_missing(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "Michinari-v1.0.0.zip"
        _write_zip(zip_path, ["Michinari/readme.txt"])

        assert extract_package(zip_path, tmp_path / "out") is None


class TestRunPackageStep:
    def test_does_nothing_without_the_option(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run_package_step(None) == []
        assert "省略" in capsys.readouterr().out

    def test_skips_when_no_package_has_been_built_yet(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # ビルド前の状態は正常なので失敗にしない。
        monkeypatch.setattr("release_smoke.find_latest_package", lambda: None)

        assert _run_package_step("latest") == []
        assert "省略" in capsys.readouterr().out

    def test_reports_a_missing_package_given_explicitly(self, tmp_path: Path) -> None:
        problems = _run_package_step(str(tmp_path / "absent.zip"))

        assert len(problems) == 1
        assert "見つかりません" in problems[0]

    def test_runs_the_smoke_for_the_latest_package(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        zip_path = tmp_path / "Michinari-v1.0.0.zip"
        _write_zip(zip_path, ["Michinari/Michinari.exe"])
        monkeypatch.setattr("release_smoke.find_latest_package", lambda: zip_path)
        monkeypatch.setattr("release_smoke.run_package_smoke", lambda _z: ["起動しませんでした"])

        assert _run_package_step("latest") == ["起動しませんでした"]


class TestCollectProblems:
    """コマンドライン実行とリリースゲートの双方が使う集約処理。"""

    def test_gathers_problems_from_every_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        database = tmp_path / "michinari.db"
        database.write_bytes(b"")
        monkeypatch.setattr("release_smoke.run_startup_smoke", lambda: ["起動しませんでした"])
        monkeypatch.setattr("release_smoke.verify_migration", lambda _s, _w: ["goal: 5 行 → 4 行"])

        problems = collect_problems(database=database)

        assert problems == ["起動しませんでした", "goal: 5 行 → 4 行"]

    def test_reports_nothing_when_every_check_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        database = tmp_path / "michinari.db"
        database.write_bytes(b"")
        monkeypatch.setattr("release_smoke.run_startup_smoke", lambda: [])
        monkeypatch.setattr("release_smoke.verify_migration", lambda _s, _w: [])

        assert collect_problems(database=database) == []

    def test_leaves_the_package_check_out_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 配布物の起動はブラウザを開くため、明示指定なしでは実行しない。
        called: list[str] = []
        monkeypatch.setattr(
            "release_smoke.run_package_smoke", lambda _z: called.append("ran") or []
        )

        collect_problems(skip_startup=True, skip_migration=True)

        assert called == []
