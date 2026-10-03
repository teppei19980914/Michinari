"""診断ログ（michinari.log）の期間指定エクスポート（Phase40 診断ログ出力・トレース強化）。

利用者が不具合に遭遇した際、自分で該当期間のログを取り出して開発者へ共有できるように
する（仕様書6.14 SC-15）。`app/desktop/logging_setup.py`が`RotatingFileHandler`で
書き出すファイル（`michinari.log`が最新、`michinari.log.1`〜`.{LOG_BACKUP_COUNT}`が
古い世代）を横断し、行頭の日時でフィルタする。
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from app.config import LOG_DIR
from app.constants.desktop import LOG_BACKUP_COUNT, LOG_FILE_NAME
from app.services.exceptions import ValidationError

#: `logging_setup.LOG_FORMAT`の`%(asctime)s`（例: "2026-09-24 07:54:33,779"）に対応する
#: 行頭パターン。一致しない行はスタックトレース等、直前の行の続き（継続行）とみなす。
_TIMESTAMP_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2},\d{3}")


def _ordered_log_files(log_dir: Path) -> list[Path]:
    """存在するログファイルを古い世代→最新（michinari.log）の順で返す。

    `RotatingFileHandler`の命名規則は`.1`が直近にローテーションされた世代、数字が
    大きいほど古い（Python標準ライブラリの仕様）。`michinari.log`（拡張子無し）が常に最新。
    """
    generations = [log_dir / f"{LOG_FILE_NAME}.{i}" for i in range(LOG_BACKUP_COUNT, 0, -1)]
    candidates = [*generations, log_dir / LOG_FILE_NAME]
    return [path for path in candidates if path.exists()]


def _filter_lines(lines: list[str], date_from: dt.date, date_to: dt.date) -> list[str]:
    """タイムスタンプ付きの主行が期間内のものだけを、続く継続行も含めて残す。"""
    kept: list[str] = []
    keep_current_group = False
    for line in lines:
        match = _TIMESTAMP_PATTERN.match(line)
        if match:
            line_date = dt.date.fromisoformat(match.group(1))
            keep_current_group = date_from <= line_date <= date_to
        if keep_current_group:
            kept.append(line)
    return kept


def export_logs(date_from: dt.date, date_to: dt.date, *, log_dir: Path = LOG_DIR) -> str:
    """指定期間（両端含む、日単位）のログを時系列順に結合して返す。

    引数:
        date_from: 開始日。
        date_to: 終了日。
        log_dir: ログ出力先フォルダ。テストから差し替えられるよう既定引数で受ける
            （`logging_setup.configure`と同じパターン）。

    返り値:
        結合後のログ本文（該当行が無ければ空文字列。存在しないこと自体はエラーではない）。

    例外:
        ValidationError: `date_to`が`date_from`より前の場合。
    """
    if date_to < date_from:
        raise ValidationError("終了日は開始日以降にしてください")

    chunks: list[str] = []
    for path in _ordered_log_files(log_dir):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        chunks.extend(_filter_lines(lines, date_from, date_to))
    return "".join(chunks)
