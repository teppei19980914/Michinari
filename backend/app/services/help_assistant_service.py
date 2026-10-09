"""ヘルプAIアシスタントの質疑応答（Phase43、仕様書8.1 AI-14、開発Todo §4）。

利用者の質問に、ヘルプ本文（`help_content.load_sections`）だけを根拠にして答える。処理の順序は
開発Todo §4 のとおり：入力検証 → 禁止語 → ヘルプ本文の組み立て（全文、超過時は選択）→
質問ごとのチャットで送信 → 出典の検証 → 後始末（チャットの削除と一覧での確認）。

質問ごとに新しいチャットを作り、回答後に削除する（1問1答）。同じチャットを使い回すと履歴が
回答に影響しうるため、質問どうしを分離する。AIへの送信は `ai_orchestration.send_and_log` を
通し、会話行は `ai_conversation.ensure_conversation` で作る
（CODING_RULES.md「AI通信とトランザクション」）。
"""

import logging
import secrets
import threading
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.ai.exceptions import AiAuthRequiredError, AiError
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_HELP,
    AI_HELP_ANSWER_MAX_CHARS,
    AI_HELP_FOLDER_NAME,
    AI_HELP_QUESTION_MAX_CHARS,
)
from app.constants.enums import AiPurpose, ConversationScope, HelpAnswerStatus
from app.constants.help_assistant import (
    CITATION_LINE_PATTERN,
    CITATION_SEPARATOR_PATTERN,
    DELIMITER_REPLACEMENTS,
    HELP_CHAT_TITLE,
    MIN_SECTION_MATCHES,
    NONCE_BYTES,
    WHITESPACE_PATTERN,
)
from app.models.ai import AiConversation, AiForbiddenTerm
from app.services import setting_reader
from app.services.exceptions import ValidationError
from app.services.help_content import HelpSection, load_sections

logger = logging.getLogger(__name__)

#: 質疑の直列化（開発Todo U12）。単一端末のため、プロセス内のロックで足りる。
_REQUEST_LOCK = threading.Lock()

#: 出典行に記載の「該当なし」（プロンプトの指示と一致させる）。出典IDとして実在しないため、
#: 検証で自然に NOT_FOUND へ落ちる。ここでは特別扱いせず、実在検証に任せる。


@dataclass(frozen=True)
class HelpAnswer:
    """ヘルプ質疑の結果。`text` は回答本文（出典行を除く）、`section_ids` は検証済みの出典ID。"""

    status: HelpAnswerStatus
    text: str
    section_ids: tuple[str, ...]


def normalize_for_match(text: str) -> str:
    """照合用に正規化する（NFKC・小文字化・空白除去）。

    全角と半角の違い、大文字と小文字の違い、空白の挿入による禁止語の回避を防ぐ。
    """
    return WHITESPACE_PATTERN.sub("", unicodedata.normalize("NFKC", text)).lower()


def sanitize_question(raw: str, max_chars: int) -> str:
    """質問を検証して整える。

    制御文字（改行以外）を取り除き、前後の空白を除く。空・上限超過は `ValidationError`。
    上限は `ai.help_question_max_chars`（呼び出し側で読んで渡す）。
    """
    cleaned = "".join(ch for ch in raw if ch == "\n" or unicodedata.category(ch) != "Cc").strip()
    if not cleaned:
        raise ValidationError("Question must not be empty")
    if len(cleaned) > max_chars:
        raise ValidationError(f"Question must be {max_chars} characters or fewer")
    return cleaned


def _contains_forbidden_term(session: Session, text: str) -> bool:
    """有効な禁止語を含むかを返す（照合は正規化後）。語が空の行は照合に使わない。"""
    normalized = normalize_for_match(text)
    terms = session.query(AiForbiddenTerm).filter(AiForbiddenTerm.enabled.is_(True)).all()
    return any(
        key and key in normalized for key in (normalize_for_match(term.term) for term in terms)
    )


def _render_section(section: HelpSection) -> str:
    """セクションをプロンプト用の文字列にする（見出しに ID を添え、出典行の根拠を明示する）。"""
    lines = [f"[セクションID: {section.id}] {section.title}", *section.body]
    return "\n".join(lines) + "\n"


def _bigrams(normalized: str) -> set[str]:
    """2文字ずつの組（日本語の語の一致を、分かち書きなしで取るため）。"""
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}


def _section_score(section: HelpSection, question_bigrams: set[str]) -> int:
    """セクションが質問の2文字の組をいくつ含むか（一致の強さ）。"""
    haystack = normalize_for_match(section.title + "".join(section.body))
    return sum(1 for gram in question_bigrams if gram in haystack)


def select_sections(
    sections: tuple[HelpSection, ...], question: str, budget: int
) -> list[HelpSection]:
    """質問に関係するセクションを、予算内で選ぶ（全文が収まらない場合にだけ使う）。

    一致が多い順に、予算に収まる範囲で採用する。採用したものは元の定義順に並べ直す。
    一致が下限（`MIN_SECTION_MATCHES`）に届かないセクションは、偶然の一致として採用しない。
    一致するセクションが1件も無ければ空のリストを返す（呼び出し側は送信せず NOT_FOUND にする）。
    """
    grams = _bigrams(normalize_for_match(question))
    ranked = sorted(
        (
            (score, index, section)
            for index, section in enumerate(sections)
            if (score := _section_score(section, grams)) >= MIN_SECTION_MATCHES
        ),
        key=lambda item: (-item[0], item[1]),
    )
    chosen: list[tuple[int, HelpSection]] = []
    used = 0
    for _, index, section in ranked:
        size = len(_render_section(section))
        if used + size <= budget:
            chosen.append((index, section))
            used += size
    return [section for _, section in sorted(chosen, key=lambda item: item[0])]


def _build_help_body(
    sections: tuple[HelpSection, ...],
    *,
    question: str,
    escaped_question: str,
    template: str,
    nonce: str,
    max_chars: int,
) -> tuple[str, list[HelpSection]]:
    """プロンプトへ入れるヘルプ本文を組み立てる（全文が予算内なら全文、超えたら選択）。

    予算は「上限 − 指示文の固定部分 − 質問」。固定部分は空の本文で組んだ長さを測って求める。
    """
    fixed = prompt_builder.build_simple(
        template, {"help_body": "", "question": "", "nonce": nonce}, max_chars
    ).prompt_chars
    budget = max_chars - fixed - len(escaped_question)
    full_body = "".join(_render_section(section) for section in sections)
    if len(full_body) <= budget:
        return full_body, list(sections)
    chosen = select_sections(sections, question, budget)
    return "".join(_render_section(section) for section in chosen), chosen


def _parse_answer(raw: str, known_ids: frozenset[str]) -> tuple[str, tuple[str, ...]]:
    """応答を、回答本文と検証済みの出典IDに分ける。

    出典行が無い、または実在しないIDしか無い場合、出典IDは空になる（呼び出し側で NOT_FOUND）。
    """
    stripped = raw.strip()
    match = CITATION_LINE_PATTERN.search(stripped)
    if match is None:
        return stripped, ()
    body = stripped[: match.start()].rstrip()
    tokens = (token.strip() for token in CITATION_SEPARATOR_PATTERN.split(match.group(1)))
    cited = tuple(dict.fromkeys(token for token in tokens if token in known_ids))
    return body, cited


def _discard_conversation(session: Session, conversation: AiConversation, folder_name: str) -> None:
    """質問ごとのチャットを削除し、一覧で削除を確認する。失敗しても回答は失わない。

    開発キットの削除の戻り値は信頼しない（開発Todo T-03）。残っていた場合はログに残し、
    会話行は削除する（利用者の画面には影響させない）。この関数は`_send_question`の
    `finally`から呼ばれるため、ここで例外を外へ出すと、既に得られた回答そのものが
    失われる（`finally`内の例外が呼び出し元の正常な戻り値を上書きするため）。
    SQLiteの書き込みロック競合（2026-10-09の不具合）等の後始末自体の失敗でこれが
    起きないよう、ここでは例外を外へ出さない。
    """
    try:
        chat_uid = conversation.conversation_uid
        try:
            ai_client.delete_chat(session, chat_uid=chat_uid)
            remains = ai_client.chat_listed_in_folder(
                session, folder_name=folder_name, chat_uid=chat_uid
            )
        except AiError:
            remains = True
        if remains:
            logger.warning("ヘルプ質問のチャットが削除されませんでした（chat_uid=%s）", chat_uid)
        session.delete(conversation)
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ヘルプ質問のチャットの後始末に失敗しました（会話行が残存の可能性）")


def _send_question(session: Session, *, prompt_text: str, prompt_chars: int) -> str:
    """質問ごとのチャットを作り、送信して、後始末を行う。応答本文を返す。"""
    folder_name = setting_reader.get_str(session, AI_HELP_FOLDER_NAME)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=None,
        scope=ConversationScope.HELP_ASSISTANT,
        scope_key=uuid.uuid4().hex,
        assistant_uid=setting_reader.get_str(session, AI_ASSISTANT_UID_HELP),
        title=HELP_CHAT_TITLE,
        folder_name=folder_name,
    )
    try:
        result = ai_orchestration.send_and_log(
            session,
            purpose=AiPurpose.HELP_ASSISTANT,
            conversation=conversation,
            prompt_text=prompt_text,
            prompt_chars=prompt_chars,
            was_truncated=False,
        )
    finally:
        _discard_conversation(session, conversation, folder_name)
    return result.response_text


def _interpret(session: Session, raw: str, sections: tuple[HelpSection, ...]) -> HelpAnswer:
    """応答を検証し、表示できる結果にする（出典・禁止語・上限の3つで判定）。"""
    body, cited = _parse_answer(raw, frozenset(section.id for section in sections))
    if not cited or not body:
        return HelpAnswer(HelpAnswerStatus.NOT_FOUND, "", ())
    max_chars = setting_reader.get_int(session, AI_HELP_ANSWER_MAX_CHARS)
    if len(body) > max_chars or _contains_forbidden_term(session, body):
        return HelpAnswer(HelpAnswerStatus.UNAVAILABLE, "", ())
    return HelpAnswer(HelpAnswerStatus.ANSWERED, body, cited)


def _answer_locked(session: Session, raw_question: str) -> HelpAnswer:
    """質疑の本体（ロックを取った状態で呼ぶ）。"""
    max_question_chars = setting_reader.get_int(session, AI_HELP_QUESTION_MAX_CHARS)
    question = sanitize_question(raw_question, max_question_chars)
    if _contains_forbidden_term(session, question):
        return HelpAnswer(HelpAnswerStatus.UNAVAILABLE, "", ())
    if not ai_client.is_authenticated(session):
        raise AiAuthRequiredError("AI connection is required")

    max_chars = ai_orchestration.get_max_prompt_chars(session)
    template = ai_orchestration.load_template_body(session, AiPurpose.HELP_ASSISTANT)
    nonce = secrets.token_hex(NONCE_BYTES)
    escaped_question = question.translate(DELIMITER_REPLACEMENTS)
    sections = load_sections()
    help_body, chosen = _build_help_body(
        sections,
        question=question,
        escaped_question=escaped_question,
        template=template,
        nonce=nonce,
        max_chars=max_chars,
    )
    if not chosen:
        return HelpAnswer(HelpAnswerStatus.NOT_FOUND, "", ())

    prompt = prompt_builder.build_simple(
        template,
        {"help_body": help_body, "question": escaped_question, "nonce": nonce},
        max_chars,
    )
    if prompt.was_truncated:
        # 末尾を切り詰めると指示文が欠落する（2026-09-14の不具合と同じ）。送らずに表示しない。
        return HelpAnswer(HelpAnswerStatus.UNAVAILABLE, "", ())

    raw = _send_question(session, prompt_text=prompt.text, prompt_chars=prompt.prompt_chars)
    return _interpret(session, raw, tuple(sections))


def ask(session: Session, *, raw_question: str) -> HelpAnswer:
    """利用者の質問に、ヘルプ本文に基づいて答える（開発Todo §4）。

    入力が不正なら `ValidationError`、AI未接続なら `AiAuthRequiredError`、通信の失敗は
    `AiError` 系を送出する（API層で HTTP に変換する）。禁止語・記載なし・表示できない回答は
    例外にせず、`HelpAnswer.status` で返す。
    """
    with _REQUEST_LOCK:
        return _answer_locked(session, raw_question)
