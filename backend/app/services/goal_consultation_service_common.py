"""目標相談チャットの質疑応答・共通処理（S09でEXAM向けに導入、S10でREADING/WORKへ展開、
開発Todo v1.1 V5）。

カテゴリ別の変数組み立て・テンプレート選択は`goal_consultation_service_exam.py`・
`_reading.py`・`_work.py`に置く（`record_service_common`/`_exam`/`_reading`/`_work`と
同じ分割方式、CODING_RULES.md置き場所ルール）。本ファイルは、カテゴリに依存しない処理
（直列化・質問の安全対策・送信・応答の解釈・相談履歴の保存）とカテゴリ分岐そのものを持つ。

処理の順序：入力検証 → 禁止語 → カテゴリ別の変数組み立て（上限超過時は週次要約→生ログの
順に古いものから縮退） → 質問ごとのチャットで送信 → 根拠の検証（プロンプトに実際に
含めた日付・週だけを採用） → 後始末（チャットの削除と一覧での確認） → 相談履歴の保存。

安全対策（禁止語・区切りの全角化・nonce・質問の検証整形）はヘルプAIアシスタントと共通の
`app.ai.question_safety`を使う（CODING_RULES.md DRYの原則、S09 U9）。質問ごとに
新しいチャットを作り、回答後に削除する（1問1答、ヘルプと同方式）。AIへの送信は
`ai_orchestration.send_and_log`を通し、会話行は`ai_conversation.ensure_conversation`で作る
（CODING_RULES.md「AI通信とトランザクション」）。
"""

import datetime as dt
import secrets
import threading
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder, question_safety
from app.ai.exceptions import AiAuthRequiredError
from app.ai.prompt_builder import DatedLogEntry
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_GOAL_CONSULTATION,
    AI_GOAL_CONSULTATION_ANSWER_MAX_CHARS,
    AI_GOAL_CONSULTATION_FOLDER_NAME,
    AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS,
)
from app.constants.enums import (
    AiPurpose,
    ConversationScope,
    GoalCategory,
    GoalConsultationAnswerStatus,
)
from app.constants.goal_consultation import (
    CITATION_TRAILER_PATTERN,
    GOAL_CONSULTATION_CHAT_TITLE,
    RECORD_CITATION_PATTERN,
    SUMMARY_CITATION_PATTERN,
)
from app.models.goal import Goal
from app.services import ai_context_common, goal_consultation_log_service, setting_reader
from app.services.exceptions import ValidationError

#: 質疑の直列化（ヘルプAIアシスタントと同方式、S09 U15）。単一端末のため、
#: プロセス内のロックで足りる。
_REQUEST_LOCK = threading.Lock()

#: {{recent_logs}}（週次要約が無い過去日の記録）が空の場合の表示。資格試験の日次報告
#: フィードバックの同名変数と同じ文言にする（`ai_context_common._NO_RECENT_LOGS_TEXT`相当、
#: CLAUDE.md DRYの原則）。
_NO_RECENT_LOGS_TEXT = "（週次要約が無い過去日の記録はありません）"


@dataclass(frozen=True)
class GoalConsultationAnswer:
    """目標相談の質疑の結果。`text`は回答本文（根拠行を除く）。`cited_dates`／`cited_weeks`は
    検証済みの根拠（プロンプトに実際に含めた日付・週だけを採用、S09 U10）。
    """

    status: GoalConsultationAnswerStatus
    text: str
    cited_dates: tuple[dt.date, ...]
    cited_weeks: tuple[tuple[dt.date, dt.date], ...]


@dataclass(frozen=True)
class CategoryContext:
    """カテゴリ別の変数組み立ての結果（開発Todo v1.1 V5）。`fixed_variables`は
    カテゴリ固有の固定変数のみ（`question`・`nonce`は本ファイルが共通で付加する）。
    `raw_entries`は`{{recent_logs}}`（週次要約が無い過去日の記録）の生ログ。
    """

    purpose: AiPurpose
    fixed_variables: dict[str, str]
    raw_entries: list[DatedLogEntry]


def _parse_answer(
    raw: str,
    valid_dates: frozenset[dt.date],
    valid_weeks: frozenset[tuple[dt.date, dt.date]],
) -> tuple[str, tuple[dt.date, ...], tuple[tuple[dt.date, dt.date], ...]] | None:
    """応答を、回答本文と検証済みの根拠（日付・週）に分ける。

    末尾の根拠行（`CITATION_TRAILER_PATTERN`）が無い場合は、出力形式の解釈に失敗したと
    判断してNoneを返す（呼び出し側でUNAVAILABLE）。根拠行中の日付・週のうち、
    `valid_dates`／`valid_weeks`（プロンプトに実際に含めた範囲）に実在しないものは採用しない。
    """
    stripped = raw.strip()
    match = CITATION_TRAILER_PATTERN.search(stripped)
    if match is None:
        return None
    body = stripped[: match.start()].rstrip()
    trailer = match.group(0)
    parsed_dates = (
        dt.date.fromisoformat(token) for token in RECORD_CITATION_PATTERN.findall(trailer)
    )
    cited_dates = tuple(dict.fromkeys(parsed for parsed in parsed_dates if parsed in valid_dates))
    parsed_weeks = (
        (dt.date.fromisoformat(start), dt.date.fromisoformat(end))
        for start, end in SUMMARY_CITATION_PATTERN.findall(trailer)
    )
    cited_weeks = tuple(dict.fromkeys(week for week in parsed_weeks if week in valid_weeks))
    return body, cited_dates, cited_weeks


def _send_question(
    session: Session, *, goal: Goal, purpose: AiPurpose, prompt_text: str, prompt_chars: int
) -> str:
    """質問ごとのチャットを作り、送信して、後始末を行う。応答本文を返す。

    `scope`は`purpose`と同じ値（`AiPurpose.GOAL_CONSULTATION*`と`ConversationScope.
    GOAL_CONSULTATION*`は文字列値を揃えている、開発Todo v1.1 V2）。
    """
    folder_name = setting_reader.get_str(session, AI_GOAL_CONSULTATION_FOLDER_NAME)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope(purpose.value),
        scope_key=uuid.uuid4().hex,
        assistant_uid=setting_reader.get_str(session, AI_ASSISTANT_UID_GOAL_CONSULTATION),
        title=GOAL_CONSULTATION_CHAT_TITLE,
        folder_name=folder_name,
    )
    try:
        result = ai_orchestration.send_and_log(
            session,
            purpose=purpose,
            conversation=conversation,
            prompt_text=prompt_text,
            prompt_chars=prompt_chars,
            was_truncated=False,
        )
    finally:
        ai_conversation.discard_conversation(session, conversation, folder_name=folder_name)
    return result.response_text


def _interpret(
    session: Session,
    raw: str,
    valid_dates: frozenset[dt.date],
    valid_weeks: frozenset[tuple[dt.date, dt.date]],
) -> GoalConsultationAnswer:
    """応答を検証し、表示できる結果にする（出力形式・禁止語・上限の3つで判定）。"""
    parsed = _parse_answer(raw, valid_dates, valid_weeks)
    if parsed is None:
        return GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
    body, cited_dates, cited_weeks = parsed
    max_chars = setting_reader.get_int(session, AI_GOAL_CONSULTATION_ANSWER_MAX_CHARS)
    too_long = len(body) > max_chars
    if not body or too_long or question_safety.contains_forbidden_term(session, body):
        return GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
    return GoalConsultationAnswer(
        GoalConsultationAnswerStatus.ANSWERED, body, cited_dates, cited_weeks
    )


def _build_category_context(session: Session, goal: Goal, today: dt.date) -> CategoryContext:
    """カテゴリ別の変数組み立てへ分岐する（`goal_consultation_service_exam/_reading/_work`は
    本モジュールの`CategoryContext`を参照するため、ここで関数内importして循環importを
    避ける。`ai_context_work.build_work_progress_summary`と同じ方式、CLAUDE.md DRYの原則）。
    """
    if goal.category is GoalCategory.EXAM:
        from app.services import goal_consultation_service_exam

        return goal_consultation_service_exam.build_context(session, goal, today)
    if goal.category is GoalCategory.READING:
        from app.services import goal_consultation_service_reading

        return goal_consultation_service_reading.build_context(session, goal, today)
    if goal.category is GoalCategory.WORK:
        from app.services import goal_consultation_service_work

        return goal_consultation_service_work.build_context(session, goal, today)
    raise ValidationError(f"Unsupported goal category: {goal.category}")  # pragma: no cover


def _answer_locked(
    session: Session, goal: Goal, today: dt.date, raw_question: str
) -> GoalConsultationAnswer:
    """質疑の本体（ロックを取った状態で呼ぶ）。"""
    max_question_chars = setting_reader.get_int(session, AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS)
    question = question_safety.sanitize_question(raw_question, max_question_chars)
    if question_safety.contains_forbidden_term(session, question):
        answer = GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
        goal_consultation_log_service.save(session, goal=goal, question=question, answer=answer)
        return answer
    if not ai_client.is_authenticated(session):
        raise AiAuthRequiredError("AI connection is required")

    category_context = _build_category_context(session, goal, today)

    # S04・S07と同じ「週次要約（圧縮）→生ログ」の2段階構成（ai_context_common参照）。
    # 目標相談は日次報告と異なり「今日」までの記録を根拠にできる（日次報告は当日分を
    # 自身の対象として除くためtarget_date-1までだが、相談は今日の記録も参照してよい）。
    compressed = ai_context_common.resolve_weekly_compressed_period(
        session, goal, period_start=goal.start_date, period_end=today
    )
    stages = ai_context_common.build_weekly_compressed_stages(
        compressed,
        raw_key="recent_logs",
        raw_entries=category_context.raw_entries,
        raw_empty_text=_NO_RECENT_LOGS_TEXT,
    )

    nonce = secrets.token_hex(question_safety.NONCE_BYTES)
    escaped_question = question.translate(question_safety.DELIMITER_REPLACEMENTS)
    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            **category_context.fixed_variables,
            "question": escaped_question,
            "nonce": nonce,
        },
        stages=stages,
    )

    template = ai_orchestration.load_template_body(session, category_context.purpose)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    # 質問文・指示文・目標概要等の固定変数は縮退しない（開発Todo 要約と縮退の設計原則）。
    # 週次要約・生ログを全て削ってもなお上限を超える場合は、切り詰めずに送信しない
    # （NewtonX利用ナレッジ「切り詰めない」、ヘルプAIアシスタントの`prompt.was_truncated`
    # 判定と同じ方針）。
    if prompt_builder.exceeds_with_entries_emptied(template, context, max_chars):
        answer = GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
        goal_consultation_log_service.save(session, goal=goal, question=question, answer=answer)
        return answer
    build_result = prompt_builder.build_with_degradable_entries(template, context, max_chars)

    # build_simpleではなくbuild_with_degradable_entriesを使っているため、
    # included_entriesは必ず設定される（app/ai/prompt_builder.py参照、S09 U20）。
    included = build_result.included_entries
    assert included is not None
    valid_dates = frozenset(entry.record_date for entry in included["recent_logs"])
    week_end_by_start = dict(compressed.covered_ranges)
    # weekly_summaries の各エントリは compressed.covered_ranges と同じ行から作られるため
    # （ai_context_common.resolve_weekly_compressed_period）、record_dateは必ず
    # week_end_by_start に存在する。
    valid_weeks = frozenset(
        (entry.record_date, week_end_by_start[entry.record_date])
        for entry in included["weekly_summaries"]
    )

    raw = _send_question(
        session,
        goal=goal,
        purpose=category_context.purpose,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
    )
    answer = _interpret(session, raw, valid_dates, valid_weeks)
    goal_consultation_log_service.save(session, goal=goal, question=question, answer=answer)
    return answer


def ask(
    session: Session, *, goal: Goal, today: dt.date, raw_question: str
) -> GoalConsultationAnswer:
    """利用者の質問に、目標の記録に基づいて答える（開発Todo v1.1 §3）。

    EXAM・READING・WORKの全カテゴリで利用できる（S10でEXAM専用ガードを撤廃、開発Todo v1.1
    V1）。入力が不正なら`ValidationError`、AI未接続なら`AiAuthRequiredError`、通信の失敗は
    `AiError`系を送出する（API層でHTTPに変換する）。禁止語・表示できない回答は例外にせず、
    `GoalConsultationAnswer.status`で返す。質問・回答は状態を問わず`goal_consultation_log`へ
    保存する（開発Todo v1.1 V8）。
    """
    with _REQUEST_LOCK:
        return _answer_locked(session, goal, today, raw_question)
