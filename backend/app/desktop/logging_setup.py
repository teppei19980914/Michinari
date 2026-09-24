"""ログのファイル出力と、標準出力が無い環境への備え（Phase37）。

コンソールを表示しない実行ファイル（PyInstallerの`--noconsole`）では、
`sys.stdin`/`sys.stdout`/`sys.stderr`が`None`になる。PyInstaller公式が明記しており
（https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html ）、この状態で
`sys.stderr.flush`のような属性へ触れると`'NoneType' object has no attribute 'flush'`で
落ちる。uvicornは既定のログ設定で標準出力へ書くため、**対処しないと起動した瞬間に
クラッシュする**。

ここでは公式が案内する対処（`None`なら`os.devnull`を開いて差し替える）を行ったうえで、
ログの実際の行き先をファイルへ向ける。コンソールが無い以上、障害調査の手がかりは
このファイルだけになる（従来は`Michinari.bat`の`pause`がその役を担っていた）。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from app.config import LOG_DIR
from app.constants.desktop import LOG_BACKUP_COUNT, LOG_FILE_NAME, LOG_MAX_BYTES
from app.middleware.request_context import RequestIdLogFilter

#: ログ1行の書式。日時・レベル・相関ID・出力元・本文。利用者が開いて読む前提で簡潔にする。
#: 相関ID（Phase40）はリクエスト外のログでは"-"になる（RequestIdLogFilter参照）。
LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def ensure_standard_streams() -> None:
    """`sys.stdout`/`sys.stderr`が`None`の場合に安全な捨て先へ差し替える。

    PyInstaller公式が案内する対処そのもの。**ログ設定より先に、起動の一番最初に呼ぶこと**
    （差し替える前にどこかが標準出力へ書くと、その時点で落ちるため）。
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 (プロセス終了まで開いたままにする)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115 (同上)


def attach_console() -> bool:  # pragma: no cover (実コンソールの割り当てのため対象外)
    """コンソールを開き、ログをそこへも流せるようにする（開発者向けの`--console`用）。

    配布する実行ファイルはコンソールを持たない構成でビルドするため、そのままでは動作中の
    ログを画面で追えない。別にコンソール版の実行ファイルを作ると配布物の大きさが倍増する
    （PyInstallerの同梱物一式がもう1組できる）ため、**実行時にコンソールを割り当てる**
    方式を採る（`AllocConsole`。Windows公式API）。

    既にコンソールへ結び付いている場合（ソースからの起動・コマンドプロンプトからの起動）は
    そのまま使う。

    返り値:
        コンソールを使える状態になったなら True。

    使用例:
        >>> attach_console()  # doctest: +SKIP
        True
    """
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # 既にコンソールがあれば AllocConsole は失敗する（＝その場合は既存のものを使う）。
        if kernel32.GetConsoleWindow() == 0 and not kernel32.AllocConsole():
            return False
        # AllocConsole の直後は標準ストリームが新しいコンソールへ向いていない。
        # 擬似ファイル CONOUT$/CONIN$ を開いて結び直す（Windowsコンソールの標準的な手順）。
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    except (OSError, AttributeError, ValueError):
        # コンソールを出せないこと自体はアプリの動作を妨げない（ログはファイルに残る）。
        return False
    return True


def resolve_log_path(log_dir: Path = LOG_DIR) -> Path:
    """ログファイルのパスを返す。

    引数:
        log_dir: 出力先フォルダ。既定は`app/config.py`の`LOG_DIR`。

    返り値:
        ログファイルのパス。
    """
    return log_dir / LOG_FILE_NAME


def configure(
    log_dir: Path = LOG_DIR, *, level: int = logging.INFO, to_console: bool = False
) -> Path:
    """ルートロガーをファイル出力へ設定する。

    世代を回す（`RotatingFileHandler`）のは、常駐して動き続けるアプリではログが際限なく
    増えるためである。

    引数:
        log_dir: 出力先フォルダ。無ければ作成する。
        level: 記録するレベルの下限。
        to_console: True なら標準出力にも同じ内容を流す（開発者向けの`--console`用）。

    返り値:
        実際のログファイルのパス（利用者へ場所を案内するために返す）。

    使用例:
        >>> configure().name
        'michinari.log'
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolve_log_path(log_dir)
    formatter = logging.Formatter(LOG_FORMAT)

    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
    ]
    if to_console:
        handlers.append(logging.StreamHandler(sys.stdout))

    root = logging.getLogger()
    root.setLevel(level)
    # 既定のハンドラ（標準出力向け）が残っていると、コンソールの無い環境で書き込みに
    # 失敗しうる。ここで組み立てたハンドラだけにする。
    for existing in list(root.handlers):
        root.removeHandler(existing)
    request_id_filter = RequestIdLogFilter()
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(request_id_filter)
        root.addHandler(handler)
    return log_path
