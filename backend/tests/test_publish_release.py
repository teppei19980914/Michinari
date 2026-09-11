"""配布パッケージのリリース公開スクリプトのテスト（scripts/publish_release.py参照）。

実際に`gh`コマンドを実行するとGitHub上へ公開されてしまうため、`subprocess.run`を
差し替えて分岐ロジックのみを検証する（`gh`自体の呼び出しは対象外）。
"""

import json
import subprocess
from pathlib import Path

import pytest
from publish_release import (
    BASE_BRANCH_REF,
    SUMMARY_END,
    SUMMARY_START,
    build_commit_path,
    build_edit_command,
    build_release_body,
    build_release_command,
    build_upload_command,
    ensure_release_tag,
    extract_summary,
    is_merged_into_base,
    publish,
    read_build_commit,
    read_remote_tag_commit,
    release_notes_path,
    release_notes_relative_path,
    release_notes_url,
    release_tag,
    release_title,
)

_SUMMARY_TEXT = "読書の記録のしかたを見直しました。"
_COMMIT = "c582f22f2ae1f238a703f1f8298e3cace4626d7c"


def _write_notes(path: Path, summary: str = _SUMMARY_TEXT) -> Path:
    path.write_text(
        f"# Michinari v1.2.3\n\n{SUMMARY_START}\n{summary}\n{SUMMARY_END}\n\n---\n\n## 詳細\n",
        encoding="utf-8",
    )
    return path


def _write_commit_record(
    path: Path, *, version: str = "1.2.3", commit: str | None = _COMMIT, dirty: bool | None = False
) -> Path:
    path.write_text(
        json.dumps({"version": version, "commit": commit, "dirty": dirty}), encoding="utf-8"
    )
    return path


def _prepared_release(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`publish`が要求するzip・詳細ノート・ビルド元コミットの記録を揃える。"""
    zip_path = tmp_path / "Michinari-v1.2.3.zip"
    zip_path.write_text("dummy", encoding="utf-8")
    return (
        zip_path,
        _write_notes(tmp_path / "v1.2.3.md"),
        _write_commit_record(tmp_path / "Michinari-v1.2.3.commit.json"),
    )


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


def test_build_release_command_verifies_the_tag_instead_of_creating_it(tmp_path: Path) -> None:
    """タグ作成をghに任せず、事前に作った正しいタグの存在確認だけを行うこと。

    `--target`を渡す方式では、同名のローカルタグがあるとghがそれをpushして指定が
    無視される（2026-09-12のv1.2.1で発生）。`--verify-tag`ならタグが無いときに中止
    されるため、取り違えたまま公開されない。
    """
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
        "--verify-tag",
        "--notes-file",
        str(body_path),
    ]
    assert "--target" not in result


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
    commit_path = _write_commit_record(tmp_path / "Michinari-v1.2.3.commit.json")

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", tmp_path / "missing.zip", notes_path, commit_path)

    assert exc.value.code == 1


def test_publish_exits_when_notes_missing(tmp_path: Path) -> None:
    zip_path = tmp_path / "Michinari-v1.2.3.zip"
    zip_path.write_text("dummy", encoding="utf-8")
    commit_path = _write_commit_record(tmp_path / "Michinari-v1.2.3.commit.json")

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, tmp_path / "missing.md", commit_path)

    assert exc.value.code == 1


class _FakeCompletedProcess:
    """`git`呼び出しの戻り値も兼ねるため、`stdout`/`stderr`も持たせる
    （publishはタグ確認で`git ls-remote`の出力を読む）。"""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_runner(calls: list[list[str]], returncodes: dict[str, int]):
    """`gh`のサブコマンド（create/edit/upload）ごとに終了コードを決める差し替え関数。

    マージ済み判定の`git`呼び出しは記録せず常に成功扱いにし、検証対象を`gh`の
    呼び出し順序だけに絞る（未マージ時の挙動は専用のテストで検証する）。
    """

    def fake_run(args, cwd=None, **kwargs):
        if args[0] == "git":
            return _FakeCompletedProcess(0)
        calls.append(args)
        return _FakeCompletedProcess(returncodes.get(args[2], 0))

    return fake_run


def test_publish_succeeds_on_first_create(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {}))

    publish("1.2.3", zip_path, notes_path, commit_path)

    assert len(calls) == 1
    assert calls[0][:3] == ["gh", "release", "create"]


def test_publish_passes_summary_body_to_gh(monkeypatch, tmp_path: Path) -> None:
    """Release本文には詳細ノートの全文ではなく要約版が渡されること。"""
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    bodies: list[str] = []

    def fake_run(args, cwd=None, **kwargs):
        if args[0] == "git":
            return _FakeCompletedProcess(0)
        bodies.append(Path(args[args.index("--notes-file") + 1]).read_text(encoding="utf-8"))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    publish("1.2.3", zip_path, notes_path, commit_path)

    assert _SUMMARY_TEXT in bodies[0]
    assert "## 詳細" not in bodies[0]


def test_publish_falls_back_to_edit_and_upload_when_create_fails(
    monkeypatch, tmp_path: Path
) -> None:
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1}))

    publish("1.2.3", zip_path, notes_path, commit_path)

    assert [call[2] for call in calls] == ["create", "edit", "upload"]


def test_publish_propagates_failure_when_edit_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1, "edit": 1}))

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, notes_path, commit_path)

    assert exc.value.code == 1
    assert [call[2] for call in calls] == ["create", "edit"]


def test_publish_propagates_failure_when_upload_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_runner(calls, {"create": 1, "upload": 1}))

    with pytest.raises(SystemExit) as exc:
        publish("1.2.3", zip_path, notes_path, commit_path)

    assert exc.value.code == 1
    assert [call[2] for call in calls] == ["create", "edit", "upload"]


def test_build_commit_path_pairs_with_the_distribution_zip(tmp_path: Path) -> None:
    assert build_commit_path(tmp_path, "1.2.3").name == "Michinari-v1.2.3.commit.json"


def test_read_build_commit_returns_recorded_commit(tmp_path: Path) -> None:
    commit_path = _write_commit_record(tmp_path / "commit.json")

    assert read_build_commit(commit_path, "1.2.3") == _COMMIT


def test_read_build_commit_aborts_when_record_is_missing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        read_build_commit(tmp_path / "missing.json", "1.2.3")


def test_read_build_commit_aborts_on_version_mismatch(tmp_path: Path) -> None:
    """別バージョンのビルド記録で公開しないこと（zipと記録の取り違え防止）。"""
    commit_path = _write_commit_record(tmp_path / "commit.json", version="1.1.0")

    with pytest.raises(SystemExit):
        read_build_commit(commit_path, "1.2.3")


def test_read_build_commit_aborts_when_built_from_dirty_tree(tmp_path: Path) -> None:
    """未コミットの木からのビルドは、対応するコミットが無いため公開しないこと。"""
    commit_path = _write_commit_record(tmp_path / "commit.json", dirty=True)

    with pytest.raises(SystemExit):
        read_build_commit(commit_path, "1.2.3")


def test_read_build_commit_aborts_when_commit_is_unrecorded(tmp_path: Path) -> None:
    commit_path = _write_commit_record(tmp_path / "commit.json", commit=None)

    with pytest.raises(SystemExit):
        read_build_commit(commit_path, "1.2.3")


def test_is_merged_into_base_checks_ancestry_against_origin_main(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, **kwargs):
        calls.append(args)
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert is_merged_into_base(tmp_path, _COMMIT) is True
    assert calls[0] == ["git", "merge-base", "--is-ancestor", _COMMIT, BASE_BRANCH_REF]


def test_is_merged_into_base_returns_false_for_unmerged_commit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(1)
    )

    assert is_merged_into_base(tmp_path, _COMMIT) is False


def test_publish_aborts_when_built_commit_is_not_merged(monkeypatch, tmp_path: Path) -> None:
    """ver1.2.0で実際に起きた「未マージのまま公開」を再発させないこと。"""
    zip_path, notes_path, commit_path = _prepared_release(tmp_path)
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, **kwargs):
        calls.append(args)
        return _FakeCompletedProcess(1 if args[0] == "git" else 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(SystemExit):
        publish("1.2.3", zip_path, notes_path, commit_path)

    assert all(call[0] == "git" for call in calls), "未マージなら gh を一切呼ばないこと"


# --- タグをビルド元コミットへ確定させる処理（2026-09-12のv1.2.1の不具合対応） ---

#: `git ls-remote`の出力はSHAと参照名をタブ区切りで返す。
_TAB = "\t"
#: v1.2.1で実際にタグが誤って指していたコミット（旧mainの先端）。
_STALE_COMMIT = "da9e566d4eca76d6ae139d59404b73039634db01"


def _tag_runner(remote_lines: str, calls: list[list[str]], local_commit: str | None = None):
    """`git ls-remote` / `git rev-list` / `git tag` / `git push` を差し替える。

    実際にタグを作成・pushするとリモートが変わってしまうため、コマンド列だけを記録する。
    """

    def fake_run(args, cwd=None, **kwargs):
        if args[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(args, 0, stdout=remote_lines, stderr="")
        if args[:2] == ["git", "rev-list"]:
            return subprocess.CompletedProcess(
                args, 0 if local_commit else 1, stdout=(local_commit or ""), stderr=""
            )
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    return fake_run


def test_read_remote_tag_commit_prefers_the_peeled_commit(monkeypatch, tmp_path: Path) -> None:
    """注釈付きタグでは`^{}`行（実体のコミット）を採ること。"""
    lines = (
        f"1111111111111111111111111111111111111111{_TAB}refs/tags/ver1.2.3\n"
        f"{_COMMIT}{_TAB}refs/tags/ver1.2.3^{{}}\n"
    )
    monkeypatch.setattr(subprocess, "run", _tag_runner(lines, []))

    assert read_remote_tag_commit(tmp_path, "ver1.2.3") == _COMMIT


def test_read_remote_tag_commit_returns_none_when_absent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", _tag_runner("", []))

    assert read_remote_tag_commit(tmp_path, "ver1.2.3") is None


def test_ensure_release_tag_creates_the_tag_at_the_built_commit(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _tag_runner("", calls))

    ensure_release_tag(tmp_path, "ver1.2.3", _COMMIT)

    assert calls[0] == ["git", "tag", "-f", "ver1.2.3", _COMMIT]
    assert calls[1] == ["git", "push", "origin", "-f", "refs/tags/ver1.2.3"]


def test_ensure_release_tag_overwrites_a_stale_local_tag(monkeypatch, tmp_path: Path) -> None:
    """公開前に作られていた古いローカルタグを、ビルド元コミットへ付け替えること。

    これが2026-09-12のv1.2.1の直接原因だった（ghが古いローカルタグをpushし、
    `--target`の指定が無視された）。
    """
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _tag_runner("", calls, local_commit=_STALE_COMMIT))

    ensure_release_tag(tmp_path, "ver1.2.3", _COMMIT)

    assert calls[0] == ["git", "tag", "-f", "ver1.2.3", _COMMIT]


def test_ensure_release_tag_is_a_noop_when_already_correct(monkeypatch, tmp_path: Path) -> None:
    """再実行しても、既に正しい位置にあるタグは触らないこと（再公開時の安全性）。"""
    calls: list[list[str]] = []
    lines = f"{_COMMIT}{_TAB}refs/tags/ver1.2.3\n"
    monkeypatch.setattr(subprocess, "run", _tag_runner(lines, calls))

    ensure_release_tag(tmp_path, "ver1.2.3", _COMMIT)

    assert calls == []


def test_ensure_release_tag_refuses_to_move_a_published_tag(monkeypatch, tmp_path: Path) -> None:
    """公開済みタグが別コミットを指す場合は、黙って動かさず中止すること。"""
    lines = f"{_STALE_COMMIT}{_TAB}refs/tags/ver1.2.3\n"
    monkeypatch.setattr(subprocess, "run", _tag_runner(lines, []))

    with pytest.raises(SystemExit):
        ensure_release_tag(tmp_path, "ver1.2.3", _COMMIT)
