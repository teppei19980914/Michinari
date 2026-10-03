"""app.config のテスト（配布パッケージ対応のデータ保存先解決、_default_data_dir）。"""

import sys
from pathlib import Path

from app import config


def test_default_data_dir_uses_repo_root_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = config._default_data_dir()

    assert result == config.REPO_ROOT / "data"


def test_default_data_dir_uses_local_app_data_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    result = config._default_data_dir()

    assert result == tmp_path / "Michinari" / "data"


def test_default_data_dir_falls_back_to_home_when_frozen_without_local_app_data(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    result = config._default_data_dir()

    assert result == Path.home() / "Michinari" / "data"
