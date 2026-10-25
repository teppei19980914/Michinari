"""添付ファイルのレスポンススキーマ（開発Todo_添付ファイル機能_v1.0）。

本文（抽出テキスト）は一覧・詳細のレスポンスに含めない（プロンプトへの注入専用で、
画面表示用途ではないため）。
"""

from pydantic import BaseModel


class AttachmentRead(BaseModel):
    """添付ファイル1件分の表示用情報（一覧・登録結果の共通形）。"""

    id: int
    file_name: str
    char_count: int


class AttachmentLimitsRead(BaseModel):
    """画面が表示・検証に使う上限（app_settingの値、A7・A10・P1）。"""

    max_file_chars: int
    max_count: int
    max_upload_size_mb: int
