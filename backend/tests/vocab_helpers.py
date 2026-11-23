"""単語帳機能のテスト用ヘルパー。"""

import datetime as dt

from sqlalchemy import select

from app.constants.enums import GoalCategory, GoalStatus, VocabCardType, VocabQuizMode
from app.models.goal import Goal
from app.models.setting import AppSetting
from app.models.vocab import VocabAnswerLog, VocabCard, VocabDeck


def make_reading_goal(
    session, name: str = "読書目標", status: GoalStatus = GoalStatus.ACTIVE
) -> Goal:
    goal = Goal(
        name=name, category=GoalCategory.READING, start_date=dt.date(2026, 1, 1), status=status
    )
    session.add(goal)
    session.flush()
    return goal


def set_setting(session, key: str, value: str) -> None:
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()


def make_deck(session, goal, name: str = "デッキ", *, use_in_ai: bool = True) -> VocabDeck:
    deck = VocabDeck(
        goal_id=goal.id, name=name, description=None, use_in_ai=use_in_ai, display_order=0
    )
    session.add(deck)
    session.flush()
    return deck


def make_card(
    session,
    deck,
    *,
    card_type: VocabCardType = VocabCardType.TERM,
    term: str = "用語",
    meaning: str = "意味",
    aliases: str | None = None,
    note: str | None = None,
    situation_text: str | None = None,
    question_text: str | None = None,
    is_checked: bool = False,
    display_order: int = 0,
) -> VocabCard:
    card = VocabCard(
        deck_id=deck.id,
        card_type=card_type,
        term=term,
        meaning=meaning,
        aliases=aliases,
        note=note,
        situation_text=situation_text,
        question_text=question_text,
        is_checked=is_checked,
        display_order=display_order,
    )
    session.add(card)
    session.flush()
    return card


def make_situation_card(
    session,
    deck,
    *,
    term: str = "見出し",
    situation_text: str = "状況",
    question_text: str | None = None,
    meaning: str = "最善の対応",
    note: str | None = None,
    is_checked: bool = False,
    display_order: int = 0,
) -> VocabCard:
    """シチュエーションカードを作る（開発Todo_単語帳_v1.0 要件F）。既定値は必須項目のみ。"""
    return make_card(
        session,
        deck,
        card_type=VocabCardType.SITUATION,
        term=term,
        meaning=meaning,
        aliases=None,
        note=note,
        situation_text=situation_text,
        question_text=question_text,
        is_checked=is_checked,
        display_order=display_order,
    )


def make_answer_log(
    session,
    card,
    *,
    mode: VocabQuizMode = VocabQuizMode.FLASH_TERM_TO_MEANING,
    is_correct: bool,
    answered_at: dt.datetime,
) -> VocabAnswerLog:
    log = VocabAnswerLog(card_id=card.id, mode=mode, is_correct=is_correct, answered_at=answered_at)
    session.add(log)
    session.flush()
    return log
