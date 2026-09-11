"""配布パッケージのリリース公開スクリプトのテスト（scripts/publish_release.py参照）。

実際に`gh`コマンドを実行するとGitHub上へ公開されてしまうため、`subprocess.run`を
差し替えて分岐ロジックのみを検証する（`gh`自体の呼び出しは対象外）。
"""

import subprocess
from pathlib import Path

import pytest
from publish_release import (
    SUMMARY_END,
    SUMMARY_START,
    build_edit_command,
    build_release_body,
    build_release_command,
    build_upload_command,
    extract_summary,
    publish,
    release_notes_path,
    release_notes_relative_path,
    release_notes_url,
    release_tag,
    release_title,
)

_SUMMARY_TEXT = "読書の記録のしかたを見直しました。"


def _write_notes(path: Path, summary: str = _SUMMARY_TEXT) -> Path:
    path.write_text(
        f"# Michinari v1.2.3\n\n{SUMMARY_START}\n{summary}\n{SUMMARY_END}\n\n---\n\n## 詳細\n",
        encoding="utf-8",
    )
    return path


def _prepared_release(tmp_path: Path) -> tuple[Path, Path]:
    """`publish`が要求するzipと詳細ノートを揃えたテンポラリ環境を用意する。"""
    zip_path = tmp_path / "Michinari-v1.2.3.zip"
    zip_path.write_text("dummy", encoding="utf-8")
    return zip_path, _write_notes(tmp_path / "v1.2.3.md")


def test_release_tag_matches_published_naming() -> None:
    """公開済みリリース（`ver1.0.0`〜`ver1.2.0`）と同じタグ命名であること。"""
    assert release_tag("1.2.3") == "ver1.2.3"


def test_release_title_matches_published_naming() -> None:
    """公開済みリリース（`Michinari-v1.2.0`）と同じ表題であること。"""
    assert release_title("1.2.3") == "Michinari-v1.2.3"


def test_release_notes_relative_path_points_to_docs_directory() -> None:
    assert release_notes_relative_path("1.2.3") == "docs/release-notes/v1.2.3.md"


def test_release_notes_path_resolves_under_repo_root(tmp_path: Path) -> None:
    assert release_notes_path(tmp_path, "1.2.3") == tmp_path / "docs/release-notes/v1.2.3.md"


def test_release_notes_url_points_to_main_branch() -> None:
    """タグではなく`main`を指すこと（過去タグには当該ファイルが存在しないため）。"""
    assert release_notes_url("1.2.3").endswith("/blob/main/docs/release-notes/v1.2.3.md")


def test_extract_summary_returns_text_between_markers(tmp_path: Path) -> None:
    notes = _write_notes(tmp_path / "v1.2.3.md")

    assert extract_summary(notes.read_text(encoding="utf-8")) == _SUMMARY_TEXT


def test_extract_summary_rejects_notes_without_markers() -> None:
    with pytest.raises(ValueError):
        extract_summary("# Michinari v1.2.3\n\n本文のみで要約ブロックが無い\n")


def test_extract_summary_rejects_reversed_markers() -> None:
    with pytest.raises(ValueError):
        extract_summary(f"{SUMMARY_END}\n要約\n{SUMMARY_START}\n")


def test_build_release_body_contains_download_summary_and_detail_link() -> None:
    body = build_release_body("1.2.3", _SUMMARY_TEXT)

    assert "Michinari-v1.2.3.zip" in body
    assert _SUMMARY_TEXT in body
    assert release_notes_url("1.2.3") in body


def test_build_release_body_stays_compact() -> None:
    """一覧ページで配布zipが埋もれないよう、導線と詳細リンクの付加は数行に収めること。"""
    overhead = build_release_body("1.2.3", "").splitlines()

    assert len([line for line in overhead if line.strip()]) <= 3


def test_build_release_command_uses_notes_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari-v1.2.3.zip"
    body_path = tmp_path / "release_body.md"

    result = build_release_command("1.2.3", zip_path, body_path)

    assert result == [
        "gh",
        "release",
        "create",
        "ver1.2.3",
        str(zip_path),
        "--title",
        "Michinari-v1.2.3",
        "--notes-file",
        str(body_path),
    ]


def test_build_edit_command_replaces_title_and_notes(tmp_path: Path) -> None:
    body_path = tmp_path / "release_body.md"

    result = build_edit_command("1.2.3", body_path)

    assert result == [
        "gh",
        "release",
        "edit",
        "ver1.2.3",
        "--title",
        "Michinari-v1.2.3",
        "--notes-file",
        str(body_path),
    ]


def test_build_upload_command_clobbers_existing_asset() -> None:
    zip_path = Path("dist/Michinari.zip")

    result = build_upload_command("1.2.3", zip_path)

    assert result == ["gh", "release", "upload", "ver1.2.3", str(zip_path), "--clobber"]


def test_publish_exits_when_zip_missing(tmp_path: Path) -> None:
    notes_path = _write_notes(tmp_path / "v1.2.3.md")

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", tmp_path / "missing.zip", notes_path)

    assert exc.value.code == 1


def test_publish_exits_when_notes_missing(tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari-v1.2.3.zip"
    zip_path.write_text("dummy", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, tmp_path / "missing.md")

    assert exc.value.code == 1


class _FakeCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _fake_runner(calls: list[list[str]], returncodes: dict[str, int]):
    """`gh`のサブコマンド（create/edit/upload）ごとに終了コードを決める差し替え関数。"""

    def fake_run(args, cwd=None):
        calls.append(args)
        return _FakeCompletedProcess(returncodes.get(args[2], 0))

    return fake_run


def test_publish_succeeds_on_first_create(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {}))

    publish("1.2.3", zip_path, notes_path)

    assert len(calls) == 1
    assert calls[0][:3] == ["gh", "release", "create"]


def test_publish_passes_summary_body_to_gh(monkeypatch, tmp_path: Path) -> None:
    """Release本文には詳細ノートの全文ではなく要約版が渡されること。"""
    zip_path, notes_path = _prepared_release(tmp_path)
    bodies: list[str] = []

    def fake_run(args, cwd=None):
        bodies.append(Path(args[args.index("--notes-file") + 1]).read_text(encoding="utf-8"))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    publish("1.2.3", zip_path, notes_path)

    assert _SUMMARY_TEXT in bodies[0]
    assert "## 詳細" not in bodies[0]


def test_publish_falls_back_to_edit_and_upload_when_create_fails(
    monkeypatch, tmp_path: Path
) -> None:
    zip_path, notes_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1}))

    publish("1.2.3", zip_path, notes_path)

    assert [call[2] for call in calls] == ["create", "edit", "upload"]


def test_publish_propagates_failure_when_edit_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1, "edit": 1}))

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, notes_path)

    assert exc.value.code == 1
    assert [call[2] for call in calls] == ["create", "edit"]


def test_publish_propagates_failure_when_upload_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1, "upload": 1}))

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, notes_path)

    assert exc.value.code == 1
    assert [call[2] for call in calls] == ["create", "edit", "upload"]
