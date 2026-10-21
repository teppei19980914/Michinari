"""目標相談チャットの質疑応答（S09、要件定義書R-104、開発Todo §4）。

資格目標（`GoalCategory.EXAM`）限定で、利用者の質問に、目標の記録（週次要約＋週次要約が
無い過去日の生ログ）・目標概要・教材の状態・品質指標の推移・リプラン履歴を根拠にして答える。
過去記録・目標概要等の組み立ては既存の`ai_context_common`／`ai_context_exam`の関数を
そのまま再利用し、再実装しない（開発Todo 要件1）。

処理の順序は開発Todo §4のとおり：入力検証 → 対象カテゴリガード → 禁止語 → 記録等の組み立て
（上限超過時は週次要約→生ログの順に古いものから縮退）→ 質問ごとのチャットで送信 → 根拠の検証
（プロンプトに実際に含めた日付・週だけを採用）→ 後始末（チャットの削除と一覧での確認）。

安全対策（禁止語・区切りの全角化・nonce・質問の検証整形）はヘルプAIアシスタントと共通の
`app.ai.question_safety`を使う（CODING_RULES.md DRYの原則、開発Todo U9）。質問ごとに
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
from app.services import ai_context_common, ai_context_exam, setting_reader
from app.services.exceptions import ValidationError

#: 質疑の直列化（ヘルプAIアシスタントと同方式、開発Todo U15）。単一端末のため、
#: プロセス内のロックで足りる。
_REQUEST_LOCK = threading.Lock()

#: {{recent_logs}}（週次要約が無い過去日の記録）が空の場合の表示。資格試験の日次報告
#: フィードバックの同名変数と同じ文言にする（`ai_context_common._NO_RECENT_LOGS_TEXT`相当、
#: CLAUDE.md DRYの原則）。
_NO_RECENT_LOGS_TEXT = "（週次要約が無い過去日の記録はありません）"


@dataclass(frozen=True)
class GoalConsultationAnswer:
    """目標相談の質疑の結果。`text`は回答本文（根拠行を除く）。`cited_dates`／`cited_weeks`は
    検証済みの根拠（プロンプトに実際に含めた日付・週だけを採用、開発Todo U10）。
    """

    status: GoalConsultationAnswerStatus
    text: str
    cited_dates: tuple[dt.date, ...]
    cited_weeks: tuple[tuple[dt.date, dt.date], ...]


def _require_exam_goal(goal: Goal) -> None:
    """対象を資格目標（EXAM）に限定する（開発Todo U7。読書・仕事はS10）。"""
    if goal.category is not GoalCategory.EXAM:
        raise ValidationError("Goal consultation is only available for exam goals")


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


def _send_question(session: Session, *, goal: Goal, prompt_text: str, prompt_chars: int) -> str:
    """質問ごとのチャットを作り、送信して、後始末を行う。応答本文を返す。"""
    folder_name = setting_reader.get_str(session, AI_GOAL_CONSULTATION_FOLDER_NAME)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.GOAL_CONSULTATION,
        scope_key=uuid.uuid4().hex,
        assistant_uid=setting_reader.get_str(session, AI_ASSISTANT_UID_GOAL_CONSULTATION),
        title=GOAL_CONSULTATION_CHAT_TITLE,
        folder_name=folder_name,
    )
    try:
        result = ai_orchestration.send_and_log(
            session,
            purpose=AiPurpose.GOAL_CONSULTATION,
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


def _answer_locked(
    session: Session, goal: Goal, today: dt.date, raw_question: str
) -> GoalConsultationAnswer:
    """質疑の本体（ロックを取った状態で呼ぶ）。"""
    _require_exam_goal(goal)
    max_question_chars = setting_reader.get_int(session, AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS)
    question = question_safety.sanitize_question(raw_question, max_question_chars)
    if question_safety.contains_forbidden_term(session, question):
        return GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
    if not ai_client.is_authenticated(session):
        raise AiAuthRequiredError("AI connection is required")

    materials = [material for material in goal.materials if material.is_active]
    # S04・S07と同じ「週次要約（圧縮）→生ログ」の2段階構成（ai_context_common参照）。
    # 目標相談は日次報告と異なり「今日」までの記録を根拠にできる（日次報告は当日分を
    # 自身の対象として除くためtarget_date-1までだが、相談は今日の記録も参照してよい）。
    compressed = ai_context_common.resolve_weekly_compressed_period(
        session, goal, period_start=goal.start_date, period_end=today
    )
    stages = ai_context_common.build_weekly_compressed_stages(
        compressed,
        raw_key="recent_logs",
        raw_entries=ai_context_exam.build_recent_study_entries(
            session, goal, goal.start_date, today
        ),
        raw_empty_text=_NO_RECENT_LOGS_TEXT,
    )

    nonce = secrets.token_hex(question_safety.NONCE_BYTES)
    escaped_question = question.translate(question_safety.DELIMITER_REPLACEMENTS)
    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "goal_summary": ai_context_exam.build_goal_summary([goal], today),
            "material_summary": ai_context_exam.build_material_summary_text(session, materials),
            "quality_trend": ai_context_exam.build_quality_trend_text(session, materials),
            "replan_history": ai_context_exam.build_replan_history_text(session, goal),
            "question": escaped_question,
            "nonce": nonce,
        },
        stages=stages,
    )

    template = ai_orchestration.load_template_body(session, AiPurpose.GOAL_CONSULTATION)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    # 質問文・指示文・目標概要等の固定変数は縮退しない（開発Todo 要約と縮退の設計原則）。
    # 週次要約・生ログを全て削ってもなお上限を超える場合は、切り詰めずに送信しない
    # （NewtonX利用ナレッジ「切り詰めない」、ヘルプAIアシスタントの`prompt.was_truncated`
    # 判定と同じ方針）。
    if prompt_builder.exceeds_with_entries_emptied(template, context, max_chars):
        return GoalConsultationAnswer(GoalConsultationAnswerStatus.UNAVAILABLE, "", (), ())
    build_result = prompt_builder.build_with_degradable_entries(template, context, max_chars)

    # build_simpleではなくbuild_with_degradable_entriesを使っているため、
    # included_entriesは必ず設定される（app/ai/prompt_builder.py参照、開発Todo U20）。
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
        session, goal=goal, prompt_text=build_result.text, prompt_chars=build_result.prompt_chars
    )
    return _interpret(session, raw, valid_dates, valid_weeks)


def ask(
    session: Session, *, goal: Goal, today: dt.date, raw_question: str
) -> GoalConsultationAnswer:
    """利用者の質問に、目標の記録に基づいて答える（開発Todo §4）。

    対象外カテゴリ・入力が不正なら`ValidationError`、AI未接続なら`AiAuthRequiredError`、
    通信の失敗は`AiError`系を送出する（API層でHTTPに変換する）。禁止語・表示できない回答は
    例外にせず、`GoalConsultationAnswer.status`で返す。
    """
    with _REQUEST_LOCK:
        return _answer_locked(session, goal, today, raw_question)
