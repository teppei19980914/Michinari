"""開発キット例外→ドメイン例外への変換（設計書 ロジック・プロンプト編16.6）。

DomainErrorのサブクラスとして定義することで、api/errors.pyの既存の変換機構
（DomainError→HTTPレスポンス）にそのまま乗せる。
"""

from app.services.exceptions import DomainError


class AiAuthRequiredError(DomainError):
    """認証関連の例外（AuthenticationError）→ AI_AUTH_REQUIRED（16.6）。"""

    def __init__(self, message: str = "AI基盤の認証が必要です") -> None:
        super().__init__(message)


class AiConfigError(DomainError):
    """設定関連の例外（ConfigurationError）→ AI_CONFIG_ERROR（16.6）。"""

    def __init__(self, message: str = "AI連携の設定が不正です") -> None:
        super().__init__(message)


class AiTimeoutError(DomainError):
    """タイムアウト（型による判定不可のため経過時間・メッセージで判定、16.6）→ AI_TIMEOUT。"""

    def __init__(self, message: str = "AI基盤の応答がタイムアウトしました") -> None:
        super().__init__(message)


class AiError(DomainError):
    """API通信・チャット関連・基本例外（APIError/ChatError/FileUploadError/NewtonXError）
    → AI_ERROR（16.6）。頻度制限に起因する可能性があるため、呼び出し側でメッセージに
    「時間をおいて再試行してください」を含める（16.6）。
    """

    def __init__(self, message: str = "AI基盤との通信に失敗しました") -> None:
        super().__init__(message)
