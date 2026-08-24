"""AI連携のリクエスト/レスポンススキーマ（データ構造編6.2、実装フェーズ分割計画書Phase5）。

PAT・トークンそのものはクライアントへ公開しない（認証状態の真偽値のみを返す、
データ構造編5.8「クライアントへの公開」）。
"""

from pydantic import BaseModel, Field


class AiStatusRead(BaseModel):
    """GET /ai/status: 認証状態とAI基盤の稼働状況。"""

    authenticated: bool
    model_status: dict[str, bool]
    login_in_progress: bool


class AiLoginRequest(BaseModel):
    """POST /ai/login: Host・PATを指定した即時認証、または未指定時はブラウザ経由の
    フォールバック認証を非同期に開始する（16.2）。
    """

    host: str | None = None
    personal_access_token: str | None = Field(default=None, min_length=1)


class AiLoginResult(BaseModel):
    #: AUTHENTICATED: PAT指定により即時認証を確認できた。PENDING: フォールバック認証を
    #: バックグラウンドで開始した（クライアントはGET /ai/statusをポーリングする、16.2）。
    status: str
    authenticated: bool


class AiAssistantRead(BaseModel):
    """GET /ai/assistants: 開発キットの実レスポンス（get_assistants()）から必要項目のみ抽出する。"""

    uid: str
    name: str
    description: str | None = None
