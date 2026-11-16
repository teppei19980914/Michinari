"""復習クイズのAI生成（開発Todo_復習クイズ_v1.0、設計書ロジック・プロンプト編17.15。
開発Todo_単語帳_v1.0 要件B B-U6で参考用語を追加）。

起動時バッチ（main.run_ai_startup_tasks、recap_generation_service.run_allの直後）から
呼ばれる。テーマの本文・紐づく報告一覧を入力にAIへ送り、出典（報告の日付）がその回の
生成に実際に使った日付集合に含まれるものだけを採用する。1ブロック（1問）の不正で
バッチ全体を無効にしない。資格試験の目標では、報告に用語・別名が出てくる単語帳カードの
意味を参考用語（{{glossary_reference}}）として併せて渡す（出典は変わらず報告の日付のまま）。
"""

import datetime as dt
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import question_safety
from app.constants.app_setting_keys import (
    QUIZ_QUESTIONS_PER_THEME,
    RECAP_CLASSIFY_CHUNK_CHARS,
    VOCAB_QUIZ_REFERENCE_MAX_CHARS,
)
from app.constants.enums import AiPurpose, ConversationScope
from app.models.goal import Goal
from app.models.quiz import QuizQuestion
from app.models.recap import RecapTheme
from app.services import (
    ai_context_exam,
    ai_context_reading,
    quiz_block_parsing,
    quiz_service,
    recap_service,
    setting_reader,
    theme_ai_dispatch,
    vocab_service,
)

_logger = logging.getLogger(__name__)

#: 他モジュール（テスト）が`quiz_generation_service._MAX_BLOCK_CHARS`として参照するため、
#: 共通モジュールの定数をこの名前空間へも引き込む（B-D3、既存テストは変更しない）。
_MAX_BLOCK_CHARS = quiz_block_parsing._MAX_BLOCK_CHARS


def _parse_blocks(response_text: str, valid_dates: frozenset[dt.date]) -> list[dict]:
    """共通解析（`quiz_block_parsing`）の結果から、出典（報告の日付）を検証する。

    出典が実在する日付の形式でない、またはその回に実際に送った日付集合に含まれない
    ブロックは個別に破棄する（1ブロックの不正でバッチ全体を無効にしない。設計書17.15参照）。
    """
    parsed: list[dict] = []
    for block in quiz_block_parsing.parse_question_blocks(response_text):
        try:
            citation_date = dt.date.fromisoformat(block.citation_raw)
        except ValueError:
            continue
        if citation_date not in valid_dates:
            continue
        parsed.append(
            {
                "question_text": block.question_text,
                "choices": block.choices,
                "correct_choice_index": block.correct_choice_index,
                "explanation": block.explanation,
                "citation_date": citation_date,
            }
        )
    return parsed


def _send(
    session: Session,
    goal: Goal,
    theme: RecapTheme,
    variables: dict[str, str],
    *,
    scope_key: str,
) -> str:
    return theme_ai_dispatch.send_theme_scoped_prompt(
        session,
        goal,
        AiPurpose.QUIZ_GENERATE,
        ConversationScope.QUIZ_GENERATE,
        variables,
        scope_key=scope_key,
        title=f"復習クイズ生成 {scope_key}（theme={theme.id}）",
    )


def generate_for_theme(session: Session, goal: Goal, theme: RecapTheme) -> int:
    """テーマについてクイズを生成する（起動時バッチ・利用者操作「作り直す」の共通処理）。

    報告が1件も無い場合は何もしない。戻り値は採用した問題数。
    """
    entries = recap_service.theme_entry_rows(session, theme)
    texts = [t for t in recap_service.entry_texts(session, entries) if t.text.strip()]
    if not texts:
        return 0
    chunk_budget = setting_reader.get_int(session, RECAP_CLASSIFY_CHUNK_CHARS)
    question_count = setting_reader.get_int(session, QUIZ_QUESTIONS_PER_THEME)
    glossary_max_chars = setting_reader.get_int(session, VOCAB_QUIZ_REFERENCE_MAX_CHARS)
    created = 0
    for chunk in recap_service.chunk_by_chars(texts, chunk_budget):
        valid_dates = frozenset(t.record_date for t in chunk)
        nonce = secrets.token_hex(question_safety.NONCE_BYTES)
        glossary_reference = vocab_service.build_glossary_reference(
            session, goal, [t.text for t in chunk], max_chars=glossary_max_chars
        ).translate(question_safety.DELIMITER_REPLACEMENTS)
        response = _send(
            session,
            goal,
            theme,
            {
                "theme_name": theme.name,
                "theme_body": theme.body,
                "entries": "\n".join(f"#{t.entry_id}（{t.record_date}）: {t.text}" for t in chunk),
                "question_count": str(question_count),
                "glossary_reference": glossary_reference,
                "nonce": nonce,
            },
            scope_key=f"theme-{theme.id}",
        )
        for block in _parse_blocks(response, valid_dates)[:question_count]:
            session.add(
                QuizQuestion(
                    theme_id=theme.id,
                    question_text=block["question_text"],
                    choice_1=block["choices"][0],
                    choice_2=block["choices"][1],
                    choice_3=block["choices"][2],
                    choice_4=block["choices"][3],
                    correct_choice_index=block["correct_choice_index"],
                    explanation=block["explanation"],
                    citation_date=block["citation_date"],
                    interval_index=0,
                    next_due_date=dt.date.today(),
                )
            )
            created += 1
        session.flush()
    return created


def regenerate_for_theme(session: Session, goal: Goal, theme: RecapTheme) -> int:
    """利用者操作「作り直す」：未出題分を削除してから生成する（開発Todo §0 U2②・U3）。"""
    quiz_service.delete_questions_for_theme(session, theme.id, only_unanswered=True)
    return generate_for_theme(session, goal, theme)


def _themes_without_quiz(session: Session, goal: Goal) -> list[RecapTheme]:
    """クイズを1件も持たないテーマ（起動時バッチの対象、積み増し防止。開発Todo §0 D12）。"""
    return list(
        session.scalars(
            select(RecapTheme)
            .where(
                RecapTheme.goal_id == goal.id,
                ~RecapTheme.id.in_(
                    select(QuizQuestion.theme_id).where(QuizQuestion.theme_id.is_not(None))
                ),
            )
            .order_by(RecapTheme.id)
        ).all()
    )


def run_all(session: Session) -> int:
    """資格試験・読書の進行中の目標すべてについて、未生成テーマのクイズを生成する
    （起動時バッチ。recap_generation_service.run_allの直後に呼ぶ）。

    1件の失敗が他の目標を止めないよう、目標ごとに取り消して続行する
    （recap_generation_service.run_allと同方式）。戻り値は生成した問題の総件数。
    """
    goals = ai_context_exam.list_active_exam_goals(
        session
    ) + ai_context_reading.list_active_reading_goals(session)
    total = 0
    for goal in goals:
        try:
            for theme in _themes_without_quiz(session, goal):
                total += generate_for_theme(session, goal, theme)
            session.commit()
        except Exception:  # noqa: BLE001 - 1件の失敗で起動時処理全体を止めないため意図的に握りつぶす
            _logger.exception("復習クイズの生成に失敗しました: goal_id=%s", goal.id)
            session.rollback()
    return total
