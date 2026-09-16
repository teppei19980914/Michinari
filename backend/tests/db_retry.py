"""OneDriveの一時的なファイルロックに対する再試行付きファイル削除
（CODING_RULES.md「置き場所ルール」＝テストでしか使わない処理はtests配下、
`migration_helpers.py`と同じ配置方針）。

本リポジトリはOneDrive同期フォルダ内にあるため、直前の`uv sync`（`.venv`配下の
パッケージ入れ替え）やテスト実行直後にファイル削除を行うと、OneDriveが同期のため
一瞬だけファイルを掴んでおり`PermissionError: [WinError 32]`になることがある
（詳細はOPERATIONS.md「配布パッケージのビルド」参照）。`backend/build.bat`・
`backend/release.bat`の`uv sync`再試行（5回×3秒＝最大15秒）と同じ待機時間を確保する。

2026-09-14、`backend/tests/conftest.py`に直接書かれていた1秒×5回（最大5秒）の再試行では
`release.bat`実行時（直前の`uv sync`直後）に不足し、リリースが2回連続で失敗する事象が
発生した。3秒×5回へ延長するとともに、`conftest.py`はモジュールインポート時に副作用
（DB削除・環境変数設定・`app.database`のインポート）を持つため単体テストできず、
再試行ロジックのみを本モジュールへ切り出してテスト対象にした。

2026-09-16、3秒×5回（最大15秒）へ延長した後もrelease.bat実行時に`PermissionError`が
再発した（直前に同一セッションで`uv sync`・`pytest`を繰り返し実行しており、OneDriveの
同期バックログが通常より長引いたと見られる）。根本対応として、テストDB自体を
OneDrive同期フォルダ外（`tempfile.gettempdir()`配下）へ移した
（`conftest.py`、`scripts/release_smoke.py`のスモークDBと同じ方針）。本モジュールの
再試行は、アンチウイルスの一時スキャン等それでも起こりうる他要因への保険として維持する。
"""

import time
from pathlib import Path

#: uv syncの再試行（backend/build.bat・backend/release.bat）と揃えた再試行回数・間隔。
UNLINK_RETRY_ATTEMPTS = 5
UNLINK_RETRY_DELAY_SECONDS = 3.0


def unlink_retrying(
    path: Path,
    *,
    attempts: int = UNLINK_RETRY_ATTEMPTS,
    delay_seconds: float = UNLINK_RETRY_DELAY_SECONDS,
) -> None:
    """`path`を削除する。OneDriveの一時的なロックによる`PermissionError`は再試行する。

    直前の`uv sync`やテスト実行（別プロセス）がファイルを閉じた直後は、OneDriveが同期の
    ため一瞬だけファイルを掴んでいることがあり、即座に`unlink()`すると失敗する。

    Args:
        path: 削除するファイルパス。
        attempts: 最大試行回数（既定5回）。
        delay_seconds: 失敗時の待機秒数（既定3秒）。
    """
    for attempt in range(1, attempts + 1):
        try:
            path.unlink()
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(delay_seconds)
