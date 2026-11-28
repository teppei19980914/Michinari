"""認証・セッションに関わるコード上の名前・サイズ定数（CODING_RULES.md 置き場所ルール）。

鍵長・Cookie名等の実装レベルの定数はここに集約する（値の重複＝ロジックの重複と同じリスク、
CODING_RULES.md DRYの原則）。業務閾値（D-20のアップロード上限等）はapp_setting相当の
仕組みではなく付録Aの方針どおり環境変数（app/config.py）で外部化するため、ここには置かない。
"""

#: セッションCookie名。
SESSION_COOKIE_NAME = "publish_session"

#: CSRF検証用リクエストヘッダ名（状態変更リクエストに必須、D-18）。
CSRF_HEADER_NAME = "X-CSRF-Token"

#: セッショントークン（Cookieへ格納する平文側）の乱数バイト数。256bit。
#: `publish_session.id`（DB側PK）にはこの値のSHA-256ハッシュを保存する（データモデル3章）。
SESSION_TOKEN_BYTES = 32

#: CSRFトークンの乱数バイト数。
CSRF_TOKEN_BYTES = 32

#: 公開APIトークン（D-19、ローカルアプリがアップロード時に使う）の乱数バイト数。
#: 開発Todo_Web公開_v1.0 10章6節で確定した初期値（32バイト＝256bit）。
API_TOKEN_BYTES = 32
