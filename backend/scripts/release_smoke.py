"""リリース前スモークテスト（実装フェーズ分割計画書 Phase 36）。

`build_package.run_tests()` が実行する pytest / tsc / vitest は「コードが仕様どおり動くか」を
検証するが、次の2点は検証していない。本スクリプトはその穴を埋める。

1. **アプリが実際に起動して応答するか** — `app/main.py` の `__main__` ブロックと `_open_browser`
   は実サーバ・実ブラウザの起動を伴うため `pragma: no cover` としており、ユニットテストの
   対象外である。スキーマ更新（Alembic）と初期データ投入を含む起動経路が通ることは、
   実際にプロセスを立ち上げて `/health` が返ることでしか確かめられない。
2. **既存の利用者データベースが移行できるか** — 空のDBへの `upgrade head` は conftest が毎回
   行っているが、既存データを持つDBへの適用は別物である（2026-08-29、既存行のコピーが
   NOT NULL 制約違反になる不具合を配布してしまった。CODING_RULES.md「DBマイグレーションの
   テスト」参照）。

実行例（backendディレクトリから）: `uv run python scripts/release_smoke.py`
（`backend/smoke.bat` をダブルクリックしても同じ）。`backend/release.bat` の前に流す。

既定では「ソースからの起動スモーク」と「実データベースの複製に対する移行確認」を行う。
いずれも一時ディレクトリ上で完結し、実行中のアプリや利用者データには触れない
（起動は空きポート、DBは複製のみを対象とする）。
"""

import argparse
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"
DATA_DIR = BACKEND_DIR.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "michinari.db"

#: 起動確認で叩くエンドポイント。画面が最初に呼ぶものを選ぶ
#: （どれか1つでも落ちれば起動失敗と見なす）。
#: `/health` はアプリの生存確認、残りは「DBを読んで200を返せるか」までを確かめる。
DEFAULT_ENDPOINTS: tuple[str, ...] = (
    "/health",
    "/api/v1/dashboard",
    "/api/v1/goals",
    "/api/v1/system-info",
)

#: 起動待ちの上限と間隔。Alembicの適用と初期データ投入を挟むため、単純なHTTPサーバより長めに取る。
STARTUP_TIMEOUT_SECONDS = 60.0
STARTUP_INTERVAL_SECONDS = 0.5

#: HTTPの応答を返す関数の型（テストから差し替えるために引数で受け取る）。
#: 戻り値はHTTPステータスコード。接続できない場合は例外を送出する。
Fetch = Callable[[str], int]


def fetch_status(url: str) -> int:
    """URLへGETしてステータスコードを返す（既定の`Fetch`実装）。"""
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 (固定のlocalhost宛)
        return int(response.status)


def find_free_port() -> int:
    """空きポートを1つ確保して返す。

    利用者が起動中のアプリ（既定8100番）と衝突させないため、固定ポートは使わない。
    OSに0番で割り当てさせた直後に閉じるため、確保から使用までの間に他プロセスへ
    奪われる可能性は残るが、開発端末での逐次実行では実用上問題にならない。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_child_env(db_path: Path, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """スモーク用プロセスへ渡す環境変数を組み立てる。

    `MICHINARI_DATABASE_URL` を一時DBへ向けることで、実行中のアプリや利用者データへ
    影響させない（`app/config.py` の `Settings` が env_prefix="MICHINARI_" で読む）。
    """
    env = dict(os.environ if base_env is None else base_env)
    env["MICHINARI_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    return env


def wait_for_health(
    fetch: Fetch,
    base_url: str,
    *,
    timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
    interval_seconds: float = STARTUP_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> bool:
    """`/health` が 200 を返すまで待つ。時間切れなら False。

    起動直後は接続自体が拒否されるため、例外は「まだ起動していない」として握りつぶす。
    """
    deadline = now() + timeout_seconds
    while True:
        try:
            if fetch(f"{base_url}/health") == 200:
                return True
        except (OSError, urllib.error.URLError):
            pass
        if now() >= deadline:
            return False
        sleep(interval_seconds)


def check_endpoints(fetch: Fetch, base_url: str, paths: Iterable[str]) -> list[str]:
    """各エンドポイントを叩き、200以外・例外になったものの説明を返す（空なら全て正常）。"""
    failures: list[str] = []
    for path in paths:
        try:
            status = fetch(f"{base_url}{path}")
        except (OSError, urllib.error.URLError) as error:
            failures.append(f"{path}: 接続できません（{error}）")
            continue
        if status != 200:
            failures.append(f"{path}: HTTP {status}")
    return failures


def table_row_counts(db_path: Path) -> dict[str, int]:
    """DB内の全テーブルの行数を返す（移行の前後比較に使う）。

    `sqlite_`で始まる内部テーブルと、Alembic自身が管理する`alembic_version`は
    利用者データではないため除く。
    """
    counts: dict[str, int] = {}
    connection = sqlite3.connect(db_path)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name <> 'alembic_version'"
            )
        ]
        for name in names:
            # テーブル名はsqlite_masterから取得した実在の識別子であり、外部入力ではない。
            counts[name] = int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
    finally:
        connection.close()
    return counts


def find_shrunk_tables(before: Mapping[str, int], after: Mapping[str, int]) -> list[str]:
    """移行によって行が減った（＝データが失われた）テーブルの説明を返す。

    移行で増えるテーブル・新設されるテーブルは正常なので対象外とする。
    """
    shrunk = []
    for name, count in before.items():
        moved = after.get(name)
        if moved is None:
            shrunk.append(f"{name}: テーブルが消えました（移行前 {count} 行）")
        elif moved < count:
            shrunk.append(f"{name}: {count} 行 → {moved} 行")
    return shrunk


def verify_migration(source_db: Path, work_dir: Path) -> list[str]:
    """実データベースの複製に対して `alembic upgrade head` を適用し、問題の説明を返す。

    複製に対して行うため、利用者のデータベースは読み取りしかしない。
    空DBへの適用は conftest が毎回行っているため、ここでの狙いは「既存データがある
    状態で適用できること」の確認である。
    """
    copied = work_dir / "michinari.db"
    shutil.copy2(source_db, copied)
    before = table_row_counts(copied)

    previous_url = os.environ.get("MICHINARI_DATABASE_URL")
    os.environ["MICHINARI_DATABASE_URL"] = f"sqlite:///{copied.as_posix()}"
    try:
        command.upgrade(Config(str(ALEMBIC_INI_PATH)), "head")
    finally:
        if previous_url is None:
            os.environ.pop("MICHINARI_DATABASE_URL", None)
        else:
            os.environ["MICHINARI_DATABASE_URL"] = previous_url

    return find_shrunk_tables(before, table_row_counts(copied))


def start_app(port: int, db_path: Path) -> subprocess.Popen[bytes]:
    """ソースからアプリを起動する（uvicorn直叩き）。

    `python -m app.main` ではなく uvicorn を直接使うのは、起動ポートが app_setting から
    決まってしまい空きポートを指定できないこと、`__main__` が実ブラウザを開くこと、
    AI基盤への通信（週次要約の遡及生成）を伴うことの3点を避けるため。
    スキーマ更新と初期データ投入は lifespan（`bootstrap_database`）で実行されるため、
    起動経路の検証という目的は満たせる。
    """
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=BACKEND_DIR,
        env=build_child_env(db_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def stop_app(process: subprocess.Popen[bytes]) -> None:
    """起動したプロセスを確実に終了させる。"""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_startup_smoke(
    *, fetch: Fetch = fetch_status, endpoints: Sequence[str] = DEFAULT_ENDPOINTS
) -> list[str]:
    """一時DB・空きポートでアプリを起動し、主要エンドポイントが応答することを確かめる。"""
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    # Windowsでは、プロセス終了直後もSQLiteのファイルハンドルが解放されず一時ディレクトリの
    # 削除がPermissionErrorになることがある。消し残るのはOSの一時領域のファイルのみで実害が
    # ないため、後片付けの失敗でスモーク全体を落とさない。
    with TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        db_path = Path(temp_dir) / "smoke.db"
        process = start_app(port, db_path)
        try:
            if not wait_for_health(fetch, base_url):
                output = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""
                return [f"起動しませんでした（{STARTUP_TIMEOUT_SECONDS:.0f}秒待機）\n{output}"]
            return check_endpoints(fetch, base_url, endpoints)
        finally:
            stop_app(process)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="リリース前スモークテスト")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="移行確認の対象とする既存データベース（既定: data/michinari.db）",
    )
    parser.add_argument("--skip-startup", action="store_true", help="起動スモークを省略する")
    parser.add_argument("--skip-migration", action="store_true", help="移行確認を省略する")
    args = parser.parse_args(argv)

    problems: list[str] = []

    if args.skip_startup:
        print("[1/2] 起動スモーク: 省略")
    else:
        print("[1/2] 起動スモークを実行しています…")
        found = run_startup_smoke()
        problems.extend(found)
        print("  → 問題なし" if not found else f"  → {len(found)} 件の問題")

    if args.skip_migration:
        print("[2/2] 移行確認: 省略")
    elif not args.database.is_file():
        # 新規環境では既存DBが無いのが正常なので、失敗にはしない。
        print(f"[2/2] 移行確認: 対象のデータベースがないため省略（{args.database}）")
    else:
        print(f"[2/2] 移行確認を実行しています…（{args.database} の複製に対して）")
        with TemporaryDirectory() as temp_dir:
            found = verify_migration(args.database, Path(temp_dir))
        problems.extend(found)
        print("  → 問題なし" if not found else f"  → {len(found)} 件の問題")

    if problems:
        print("\nスモークテストで問題が見つかりました:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nスモークテストは全て通過しました。")
    return 0


if __name__ == "__main__":  # pragma: no cover (コマンドラインからの実行のみ)
    sys.exit(main())
