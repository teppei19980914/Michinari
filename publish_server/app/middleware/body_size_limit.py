"""リクエストボディサイズの上限値算出（開発Todo_Web公開_v1.0 単位2、D-20・STRIDE分析5章
「巨大ペイロード送信によるリソース枯渇」）。

自前のASGIミドルウェア実装（`receive()`をラップして例外を送出する方式）を最初に試みたが、
実機検証でFastAPI本体のリクエストボディ読み込み処理（`fastapi/routing.py`の
`get_request_handler`）が、ボディ読み込み中の`Exception`を`except Exception as e: ... raise
HTTPException(status_code=400, ...)`で一律400へ変換してしまい、413を返せないことが判明した
（`HTTPException`サブクラスにしても同様の変換経路を通ってしまい解消しなかった）。

FastAPI/Starletteには、まさにこの目的のために一次サポートされた仕組み
（`starlette.middleware.body_limit.RequestBodyLimitMiddleware`、`FastAPI(max_body_size=...)`
引数。インストール済みパッケージのソース`.venv/Lib/site-packages/starlette/middleware/
body_limit.py`・`fastapi/_body_limit.py`で確認済み、バージョン25.11〈fastapi 0.165.0〉が同梱する
`fastapi/.agents/skills/fastapi/SKILL.md`「Request Body Limits」節にも記載がある一次情報源）が
既に存在する。これは`Content-Length`ヘッダだけでなく実際の受信バイト数（ストリーミング中）も
数えるため、`Transfer-Encoding: chunked`による迂回を構造的に防ぎ、二重送信も内部で防止済み
（`response_started`フラグ）。自前実装は撤回し、`app/main.py`の`create_app()`がこの一次
サポート機能を`FastAPI(max_body_size=...)`として使う（本モジュールは閾値の算出のみ担う）。

閾値は`create_app()`実行時に1回だけ評価する（Starletteの`max_body_size`はASGIアプリ構築時に
固定される設計のため、同ファイルのCORS許可オリジンと同じ扱い）。超過時のレスポンス本文は
FastAPI既定の`{"detail": "Content Too Large"}`（413）になる（この一次サポート機能は内部で
`fastapi.exception_handlers.http_exception_handler`を直接呼ぶため、アプリ独自のエラー形式
`{"error": {"code": ..., "message": ...}}`へは揃えられない。D-20の正確な上限判定・専用エラー
コード〈SNAPSHOT_TOO_LARGE等〉は依然として`app/services/publish_service.py`の
`_check_snapshot_size`が担う。本モジュールはJSONパース前の粗い事前防御に過ぎない）。
"""

from app.config import get_settings

#: スナップショット本体（items/cards/questions）以外のラッパーフィールド（`goal_name`等）分の
#: オーバーヘッドを許容するための緩いバッファ。
OVERHEAD_FACTOR = 2


def compute_max_body_size() -> int:
    return get_settings().max_snapshot_bytes * OVERHEAD_FACTOR
