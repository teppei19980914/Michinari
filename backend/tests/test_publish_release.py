"""配布パッケージのリリース公開スクリプトのテスト（scripts/publish_release.py参照）。

実際に`gh`コマンドを実行するとGitHub上へ公開されてしまうため、`subprocess.run`を
差し替えて分岐ロジックのみを検証する（`gh`自体の呼び出しは対象外）。
"""

import subprocess
from pathlib import Path

from publish_release import (
    build_release_command,
    build_upload_command,
    publish,
    release_tag,
    release_title,
)


def test_release_tag_matches_published_naming() -> None:
    """公開済みリリース（`ver1.0.0`/`ver1.1.0`）と同じタグ命名であること。"""
    assert release_tag("1.2.3") == "ver1.2.3"


def test_release_title_matches_published_naming() -> None:
    """公開済みリリース（`Michinari-v1.1.0`）と同じ表題であること。"""
    assert release_title("1.2.3") == "Michinari-v1.2.3"


def test_build_release_command_uses_published_tag_and_title() -> None:
    zip_path = Path("dist/Michinari.zip")

    result = build_release_command("1.2.3", zip_path)

    assert result == [
        "gh",
        "release",
        "create",
        "ver1.2.3",
        str(zip_path),
        "--title",
        "Michinari-v1.2.3",
        "--generate-notes",
    ]


def test_build_upload_command_clobbers_existing_asset() -> None:
    zip_path = Path("dist/Michinari.zip")

    result = build_upload_command("1.2.3", zip_path)

    assert result == ["gh", "release", "upload", "ver1.2.3", str(zip_path), "--clobber"]


def test_publish_exits_when_zip_missing(tmp_path: Path) -> None:
    missing_zip = tmp_path / "Michinari.zip"

    try:
        publish("1.2.3", missing_zip)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 1
    assert raised


class _FakeCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_publish_succeeds_on_first_create(monkeypatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari.zip"
    zip_path.write_text("dummy", encoding="utf-8")
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    publish("1.2.3", zip_path)

    assert len(calls) == 1
    assert calls[0][:3] == ["gh", "release", "create"]


def test_publish_falls_back_to_upload_when_create_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari.zip"
    zip_path.write_text("dummy", encoding="utf-8")
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        return _FakeCompletedProcess(0 if args[2] == "upload" else 1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    publish("1.2.3", zip_path)

    assert len(calls) == 2
    assert calls[1][:3] == ["gh", "release", "upload"]


def test_publish_propagates_failure_when_upload_also_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari.zip"
    zip_path.write_text("dummy", encoding="utf-8")

    def fake_run(args, cwd=None):
        return _FakeCompletedProcess(1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        publish("1.2.3", zip_path)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 1
    assert raised
