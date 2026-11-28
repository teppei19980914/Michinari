"""認証APIのリクエスト・レスポンススキーマ。

文字数の上限はpydantic層でも検証する（`app/services/account_service.py`のサービス層検証と
二重になるが、巨大な入力がargon2ハッシュ化まで到達する前に拒否するための防御、STRIDE分析
5章「D:サービス停止」対策と同じ考え方）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants.validation import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)


class AccountCreateRequest(BaseModel):
    username: str = Field(min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class AccountResponse(BaseModel):
    # `LoginResponse`組み立て時に`PublishAccount`ORMインスタンスをそのまま渡すため必要
    # （FastAPIがresponse_modelとして直接返す場合はfrom_attributes=Trueを内部で付与するが、
    # ここは`app/api/auth.py`のlogin()がPythonコードで明示的に`LoginResponse(...)`を
    # 構築するため、モデル自身の設定が必要）。
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class LoginResponse(BaseModel):
    account: AccountResponse
    #: 状態変更リクエストの`X-CSRF-Token`ヘッダへ付与する値（D-18）。このレスポンス本文でのみ返す。
    csrf_token: str


class ApiTokenCreateResponse(BaseModel):
    id: int
    #: 平文トークン。この応答でのみ返す（D-19、以後はハッシュのみ保存）。
    token: str
    created_at: datetime


class ApiTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
