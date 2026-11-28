"""サービス層のドメイン例外（publish_server独自実装、D-24）。

CLAUDE.md「サービス層でのHTTP例外の送出」禁止に従い、HTTPExceptionではなくここに定義する
ドメイン例外を送出する。HTTPステータスへの変換はAPI層（app/api/errors.py）で行う。
backend/app/services/exceptions.pyとは別実装であり、import依存を持たない
（publish_serverはbackendとは別プロセス・別デプロイ単位のため）。

例外メッセージの文字列はCODING_RULES.md「①DRYの原則」に倣い英語で書く（サーバログにのみ出し、
画面文言はAPI層のcodeから別途解決する）。
"""


class DomainError(Exception):
    """publish_serverのサービス層が送出する例外の基底クラス。"""


class ValidationError(DomainError):
    """入力値検証エラー。"""


class UsernameAlreadyExistsError(DomainError):
    """アカウント作成時、ユーザー名が既に使われている場合。"""

    def __init__(self) -> None:
        super().__init__("This username is already taken")


class InvalidCredentialsError(DomainError):
    """ユーザー名またはパスワードが誤っている場合。

    STRIDE分析（開発Todo_Web公開_v1.0 5章）「エラーメッセージからユーザー存在有無が
    判別可能」を避けるため、ユーザー名不存在・パスワード不一致・ログイン試行回数制限に
    よる一時ロック中（D-17）のいずれでも同じ例外・同じメッセージにする（専用の
    ACCOUNT_LOCKEDコードは意図的に設けない。ロック状態だけが別コードで判別できると、
    総当たりで対象ユーザー名の存在有無が分かってしまうため）。
    """

    def __init__(self) -> None:
        super().__init__("Username or password is incorrect")


class SessionRequiredError(DomainError):
    """セッションCookieが無い、または無効・期限切れの場合。"""

    def __init__(self) -> None:
        super().__init__("A valid session is required")


class CsrfTokenInvalidError(DomainError):
    """CSRFトークンが無い、または一致しない場合（D-18）。"""

    def __init__(self) -> None:
        super().__init__("CSRF token is missing or invalid")


class TokenNotFoundError(DomainError):
    """指定されたAPIトークンIDが、ログイン中のアカウントに属さない場合（D-21、認可境界）。"""

    def __init__(self, token_id: int) -> None:
        self.token_id = token_id
        super().__init__(f"PublishApiToken(id={token_id}) not found")
