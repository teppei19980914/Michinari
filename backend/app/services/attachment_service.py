"""添付ファイル機能（開発Todo_添付ファイル機能_v1.0）。

利用者が登録したPDFからテキストを抽出し、goal非依存の共通プール（`attachment`）へ保存する。
PDF原本は保存しない（A2）。登録・一覧・削除・選択ファイルからのプロンプト注入用テキスト
組み立て（`build_attachment_block`）を担う。
"""

import io
from dataclasses import dataclass

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.ai.question_safety import DELIMITER_REPLACEMENTS, contains_forbidden_term
from app.constants.app_setting_keys import (
    AI_ATTACHMENT_MAX_COUNT,
    AI_ATTACHMENT_MAX_FILE_CHARS,
    AI_ATTACHMENT_MAX_UPLOAD_SIZE_MB,
)
from app.models.attachment import Attachment
from app.services import setting_reader
from app.services.exceptions import NotFoundError, ValidationError

#: 抽出テキストがこの文字数未満の場合は抽出失敗（画像のみのページ等、A4）とみなして
#: 登録を拒否する（P10）。利用者が調整する値ではなく抽出の技術的な妥当性確認のための
#: 内部閾値のため、app_setting化はしない（question_safety.NONCE_BYTESと同じ位置づけ）。
_MIN_EXTRACTED_TEXT_CHARS = 50


@dataclass(frozen=True)
class AttachmentEntry:
    """添付ファイル1件分の表示用情報（本文は含まない、一覧表示用）。

    API層のPydanticスキーマ`schemas.attachment.AttachmentRead`とは別物（サービス層の
    内部DTOは`Entry`/`Summary`等で終える既存命名慣習に合わせ、スキーマ層の`*Read`接尾語と
    名前を揃えない。例: `ReadingLogEntry`・`GoalConsultationLogEntry`）。
    """

    id: int
    file_name: str
    char_count: int


@dataclass(frozen=True)
class AttachmentLimits:
    """添付ファイルの上限値（画面側の事前チェック用、A7・A10・P1）。"""

    max_file_chars: int
    max_count: int
    max_upload_size_mb: int


def get_limits(session: Session) -> AttachmentLimits:
    return AttachmentLimits(
        max_file_chars=setting_reader.get_int(session, AI_ATTACHMENT_MAX_FILE_CHARS),
        max_count=setting_reader.get_int(session, AI_ATTACHMENT_MAX_COUNT),
        max_upload_size_mb=setting_reader.get_int(session, AI_ATTACHMENT_MAX_UPLOAD_SIZE_MB),
    )


def _extract_text(content: bytes) -> str:
    """PDFバイト列からテキストを抽出する（A3・A4、OCRは行わない）。

    pypdfは壊れた・悪意ある構造（異常なxref・深いネスト等）に対し`PdfReadError`／
    `ValueError`以外の例外（`RecursionError`等）を投げることがあるため、広く捕捉して
    `ValidationError`へ変換する（injection-reviewer指摘、2026-10-25）。
    """
    try:
        reader = PdfReader(io.BytesIO(content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValidationError("Uploaded file is not a readable PDF") from exc
    return "\n".join(pages_text).strip()


def register(session: Session, *, file_name: str, content: bytes) -> Attachment:
    """PDFを検証・テキスト抽出して登録する（A2・A3・A4・A7・A10・P1・P10・P12①）。

    検証に失敗した場合は何も保存しない（ValidationError）。
    """
    if not file_name.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are supported")

    limits = get_limits(session)
    max_upload_bytes = limits.max_upload_size_mb * 1024 * 1024
    if len(content) == 0:
        raise ValidationError("Uploaded file is empty")
    if len(content) > max_upload_bytes:
        raise ValidationError(
            f"Uploaded file must be {limits.max_upload_size_mb}MB or smaller"
        )

    current_count = session.query(Attachment).count()
    if current_count >= limits.max_count:
        raise ValidationError(f"Attachment count must be {limits.max_count} or fewer")

    extracted_text = _extract_text(content)
    if len(extracted_text) < _MIN_EXTRACTED_TEXT_CHARS:
        raise ValidationError(
            "Could not extract enough text from this PDF (image-only pages are not supported)"
        )
    if len(extracted_text) > limits.max_file_chars:
        raise ValidationError(
            f"Extracted text must be {limits.max_file_chars} characters or fewer"
        )
    if contains_forbidden_term(session, extracted_text) or contains_forbidden_term(
        session, file_name
    ):
        raise ValidationError("File name or extracted text contains a forbidden term")

    attachment = Attachment(
        file_name=file_name, extracted_text=extracted_text, char_count=len(extracted_text)
    )
    session.add(attachment)
    session.flush()
    return attachment


def list_all(session: Session) -> list[AttachmentEntry]:
    """登録順（id昇順）で一覧を返す。"""
    rows = session.query(Attachment).order_by(Attachment.id).all()
    return [
        AttachmentEntry(id=row.id, file_name=row.file_name, char_count=row.char_count)
        for row in rows
    ]


def delete(session: Session, attachment_id: int) -> None:
    """添付ファイルを削除する（P3：常に削除を許可する。中間テーブルの行のみCASCADEで消え、
    参照元の対話・質問ログ本体は残る）。
    """
    row = session.get(Attachment, attachment_id)
    if row is None:
        raise NotFoundError("Attachment", attachment_id)
    session.delete(row)
    session.flush()


def get_many_or_raise(session: Session, attachment_ids: list[int]) -> list[Attachment]:
    """指定IDの添付ファイルを取得する。1件でも存在しない場合はNotFoundError。

    重複IDは1件に正規化し、選択件数が保持上限（`ai.attachment_max_count`）を超える場合は
    拒否する。正規化前の入力をそのまま`build_attachment_block`へ渡すと、同じIDを多数回
    指定するだけで連結文字列を増幅できてしまう（injection-reviewer指摘、2026-10-25）。
    """
    if not attachment_ids:
        return []
    unique_ids = list(dict.fromkeys(attachment_ids))
    limits = get_limits(session)
    if len(unique_ids) > limits.max_count:
        raise ValidationError(f"Attachment selection must be {limits.max_count} or fewer")
    rows = session.query(Attachment).filter(Attachment.id.in_(unique_ids)).all()
    found_ids = {row.id for row in rows}
    missing = [aid for aid in unique_ids if aid not in found_ids]
    if missing:
        raise NotFoundError("Attachment", missing[0])
    by_id = {row.id: row for row in rows}
    return [by_id[aid] for aid in unique_ids]


def build_attachment_block(session: Session, attachments: list[Attachment]) -> str:
    """選択された添付ファイルから、プロンプト注入用のテキストを組み立てる（A6・A11）。

    禁止語は保存後に追加される可能性があるため、送信直前に再照合する（P12②、
    `_build_conversation_history`のW3と同じ理由）。1件でも一致したら送信全体を中止する
    （会話履歴のように黒子で除外すると、選んだファイルが使われないという不可解な体験に
    なるため、ValidationErrorで明示して中止する）。

    空リストの場合は空文字を返す（呼び出し元が用途ごとの空表示文言に差し替える、
    `prompt_builder._join_dated_entries`と同じ役割分担）。
    """
    if not attachments:
        return ""
    for attachment in attachments:
        if contains_forbidden_term(session, attachment.extracted_text) or contains_forbidden_term(
            session, attachment.file_name
        ):
            raise ValidationError(
                f"Attachment(id={attachment.id}) contains a forbidden term"
            )
    # 区切り（<<<ATTACHMENTS-{{nonce}}>>>等）の偽造を防ぐため、山括弧を全角化する
    # （question_safety.DELIMITER_REPLACEMENTS、nonceと併用する二重の防御。P11）。
    # file_nameは利用者がアップロード時に指定するため、本文と同様に偽造対象になりうる。
    return "\n\n".join(
        f"【{attachment.file_name.translate(DELIMITER_REPLACEMENTS)}】\n"
        f"{attachment.extracted_text.translate(DELIMITER_REPLACEMENTS)}"
        for attachment in attachments
    )
