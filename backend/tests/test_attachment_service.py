"""添付ファイル機能のサービス層テスト（開発Todo_添付ファイル機能_v1.0）。

PDFの登録・一覧・削除・選択ファイルからのプロンプト注入用テキスト組み立てを検証する。
PDFはpdf_helpers.build_minimal_pdf/build_pdf_without_textで都度生成する
（実ファイルを持たず、既存のai_context_helpers.pyと同じ方針）。
"""

import pytest

from app.constants.app_setting_keys import (
    AI_ATTACHMENT_MAX_COUNT,
    AI_ATTACHMENT_MAX_FILE_CHARS,
    AI_ATTACHMENT_MAX_UPLOAD_SIZE_MB,
)
from app.models.ai import AiForbiddenTerm
from app.models.attachment import Attachment
from app.services import attachment_service
from app.services.exceptions import NotFoundError, ValidationError
from tests.pdf_helpers import build_minimal_pdf, build_pdf_without_text


def _set_setting(session, key, value):
    from app.models.setting import AppSetting

    row = session.query(AppSetting).filter(AppSetting.key == key).one()
    row.value = value
    session.commit()


def _add_term(session, term, *, enabled=True):
    session.add(AiForbiddenTerm(term=term, enabled=enabled, note=None))
    session.commit()


#: attachment_service._MIN_EXTRACTED_TEXT_CHARS（50字）以上の長さを持つサンプル文面
#: （DRYの原則。各テストが個別に50字以上の文字列を書くと長さの意図が埋もれるため集約する）。
_SAMPLE_TEXT_A = "document a content, long enough to pass the minimum length check"
_SAMPLE_TEXT_B = "document b content, long enough to pass the minimum length check"


# --- register ---


def test_register_extracts_text_and_saves(seeded_session):
    pdf_bytes = build_minimal_pdf(_SAMPLE_TEXT_A)
    attachment = attachment_service.register(
        seeded_session, file_name="exam.pdf", content=pdf_bytes
    )

    assert attachment.id is not None
    assert attachment.file_name == "exam.pdf"
    assert attachment.extracted_text == _SAMPLE_TEXT_A
    assert attachment.char_count == len(_SAMPLE_TEXT_A)
    # PDF原本は保持しない（A2）。
    saved = seeded_session.get(Attachment, attachment.id)
    assert saved.extracted_text == _SAMPLE_TEXT_A


def test_register_rejects_non_pdf_extension(seeded_session):
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session, file_name="notes.txt", content=b"some text content here"
        )
    assert seeded_session.query(Attachment).count() == 0


def test_register_rejects_empty_file(seeded_session):
    with pytest.raises(ValidationError):
        attachment_service.register(seeded_session, file_name="empty.pdf", content=b"")


def test_register_rejects_file_exceeding_size_limit(seeded_session):
    _set_setting(seeded_session, AI_ATTACHMENT_MAX_UPLOAD_SIZE_MB, "1")
    oversized = b"x" * (2 * 1024 * 1024)
    with pytest.raises(ValidationError):
        attachment_service.register(seeded_session, file_name="big.pdf", content=oversized)


def test_register_rejects_when_count_limit_reached(seeded_session):
    _set_setting(seeded_session, AI_ATTACHMENT_MAX_COUNT, "1")
    attachment_service.register(
        seeded_session, file_name="first.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session, file_name="second.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_B)
        )


def test_register_rejects_corrupted_pdf(seeded_session):
    """PDFとして読み取れないバイト列（破損・不正な構造）は登録を拒否する（A3・A4）。"""
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session,
            file_name="corrupted.pdf",
            content=b"%PDF-1.4\nnot a valid pdf structure at all, just garbage bytes here",
        )
    assert seeded_session.query(Attachment).count() == 0


def test_register_rejects_pdf_with_no_extractable_text(seeded_session):
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session, file_name="image-only.pdf", content=build_pdf_without_text()
        )


def test_register_rejects_text_exceeding_file_char_limit(seeded_session):
    _set_setting(seeded_session, AI_ATTACHMENT_MAX_FILE_CHARS, "10")
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session,
            file_name="long.pdf",
            content=build_minimal_pdf("this text is definitely longer than ten characters"),
        )


def test_register_rejects_forbidden_term_in_extracted_text(seeded_session):
    # build_minimal_pdfはHelvetica（WinAnsiEncoding）のみを使うため、テスト対象の
    # 禁止語はASCIIで表現する（latin-1でエンコードできない文字は使えない）。
    _add_term(seeded_session, "forbiddenword")
    with pytest.raises(ValidationError):
        attachment_service.register(
            seeded_session,
            file_name="forbidden.pdf",
            content=build_minimal_pdf(
                "this document definitely contains forbiddenword somewhere inside it"
            ),
        )
    assert seeded_session.query(Attachment).count() == 0


# --- list_all / delete ---


def test_list_all_returns_registration_order(seeded_session):
    first = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )
    second = attachment_service.register(
        seeded_session, file_name="b.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_B)
    )

    result = attachment_service.list_all(seeded_session)

    assert [entry.id for entry in result] == [first.id, second.id]
    assert result[0].file_name == "a.pdf"
    assert result[0].char_count == len(_SAMPLE_TEXT_A)


def test_delete_removes_attachment(seeded_session):
    attachment = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )

    attachment_service.delete(seeded_session, attachment.id)

    assert seeded_session.get(Attachment, attachment.id) is None


def test_delete_raises_not_found_for_missing_id(seeded_session):
    with pytest.raises(NotFoundError):
        attachment_service.delete(seeded_session, 999)


# --- get_many_or_raise ---


def test_get_many_or_raise_returns_empty_list_for_empty_ids(seeded_session):
    assert attachment_service.get_many_or_raise(seeded_session, []) == []


def test_get_many_or_raise_returns_requested_order(seeded_session):
    first = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )
    second = attachment_service.register(
        seeded_session, file_name="b.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_B)
    )

    result = attachment_service.get_many_or_raise(seeded_session, [second.id, first.id])

    assert [entry.id for entry in result] == [second.id, first.id]


def test_get_many_or_raise_raises_not_found_for_missing_id(seeded_session):
    attachment = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )

    with pytest.raises(NotFoundError):
        attachment_service.get_many_or_raise(seeded_session, [attachment.id, 999])


def test_get_many_or_raise_deduplicates_repeated_ids(seeded_session):
    """同じIDを多数回指定しても1件分にしか展開されない（プロンプト肥大化の防止、
    injection-reviewer指摘）。"""
    attachment = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )

    result = attachment_service.get_many_or_raise(
        seeded_session, [attachment.id, attachment.id, attachment.id]
    )

    assert [entry.id for entry in result] == [attachment.id]


def test_get_many_or_raise_rejects_selection_exceeding_max_count(seeded_session):
    """重複除去後の選択件数が保持上限を超える場合は拒否する。"""
    _set_setting(seeded_session, AI_ATTACHMENT_MAX_COUNT, "2")
    first = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )
    second = attachment_service.register(
        seeded_session, file_name="b.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_B)
    )
    third_id = max(first.id, second.id) + 1

    with pytest.raises(ValidationError):
        attachment_service.get_many_or_raise(seeded_session, [first.id, second.id, third_id])


# --- build_attachment_block ---


def test_build_attachment_block_returns_empty_string_for_no_attachments(seeded_session):
    assert attachment_service.build_attachment_block(seeded_session, []) == ""


def test_build_attachment_block_joins_file_name_and_text(seeded_session):
    first = attachment_service.register(
        seeded_session, file_name="a.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_A)
    )
    second = attachment_service.register(
        seeded_session, file_name="b.pdf", content=build_minimal_pdf(_SAMPLE_TEXT_B)
    )

    block = attachment_service.build_attachment_block(seeded_session, [first, second])

    assert "【a.pdf】" in block
    assert _SAMPLE_TEXT_A in block
    assert "【b.pdf】" in block
    assert _SAMPLE_TEXT_B in block


def test_build_attachment_block_rejects_forbidden_term_added_after_registration(seeded_session):
    """禁止語は登録後に追加される可能性があるため、送信直前に再照合する（P12②）。"""
    attachment = attachment_service.register(
        seeded_session,
        file_name="a.pdf",
        content=build_minimal_pdf(
            "this document content is completely harmless and safe text"
        ),
    )
    _add_term(seeded_session, "harmless")

    with pytest.raises(ValidationError):
        attachment_service.build_attachment_block(seeded_session, [attachment])
