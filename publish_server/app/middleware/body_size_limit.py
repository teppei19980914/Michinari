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
固定される設計のため、同ファイルのCORS許可オリジンと同じ扱い）。

超過時の実際のレスポンス（実機確認済み、auth-reviewerレビュー2026-11-28）：
`Content-Type: text/plain`・本文`Content Too Large`（413）。アプリ独自のJSONエラー形式
`{"error": {"code": ..., "message": ...}}`にはならず、`register_security_headers_middleware`
（CSP等）・CORSMiddlewareも付与されない（`RequestBodyLimitMiddleware`が`app.add_middleware`で
登録したミドルウェア群よりも外側で直接レスポンスを送るため、FastAPI/Starletteのミドルウェア
スタック構造上の仕様であり本コードの配線ミスではない）。本文が固定文字列のみで攻撃者制御の
内容を反映しないため、CSP・X-Frame-Options等の欠落がXSS等に直結する経路は無い（LOW、
対応は見送り。D-20の正確な上限判定・専用エラーコード〈SNAPSHOT_TOO_LARGE等〉は依然として
`app/services/publish_service.py`の`_check_snapshot_size`が担う。本モジュールはJSONパース前の
粗い事前防御に過ぎない）。
"""

from app.config import get_settings

#: スナップショット本体（items/cards/questions）以外のラッパーフィールド（`goal_name`等）分の
#: オーバーヘッドを許容するための緩いバッファ。
OVERHEAD_FACTOR = 2


def compute_max_body_size() -> int:
    return get_settings().max_snapshot_bytes * OVERHEAD_FACTOR
