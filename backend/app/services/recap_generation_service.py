"""振り返り（テーマ累積）のAI分類とテーマ本文の更新（資格試験・読書の目標ごと）。

起動時バッチ（main.run_ai_startup_tasks）から呼ばれる。報告の取り込みと分類結果の解釈は
recap_service が担い、本モジュールはそれをAI呼び出しで埋める。

網羅性を守るため、AIの応答が既存の本文を下回る長さだった場合は採用せず、その回の分類を
取り消して次回のバッチで再処理する（内容を失うより再処理を選ぶ）。
"""

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    RECAP_BODY_MAX_CHARS,
    RECAP_CLASSIFY_CHUNK_CHARS,
    RECAP_MIN_RETENTION_RATIO,
)
from app.constants.enums import AiPurpose, ConversationScope, GoalCategory
from app.constants.recap import (
    RECAP_BODY_EMPTY_PLACEHOLDER,
    RECAP_CONVERSATION_TITLE_PREFIX,
    RECAP_NO_THEMES_PLACEHOLDER,
)
from app.models.goal import Goal
from app.models.recap import RecapTheme
from app.services import ai_context_service, recap_service, setting_reader
from app.services.exceptions import RecapBodyRejectedError, RecapPromptTooLongError

#: 目標種別ごとの既存アシスタント（新しい設定項目は増やさない。週次要約用を流用する）。
_ASSISTANT_KEY_BY_CATEGORY = {
    GoalCategory.EXAM: AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    GoalCategory.READING: AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
}


def run_for_goal(session: Session, goal: Goal, today: dt.date) -> int:
    """目標1件について、未分類の報告を分類し、影響を受けたテーマの本文を更新する。

    当日の報告は編集中の可能性があるため対象外（前日までを対象にする）。戻り値は分類した
    報告の件数。

    チャンク（分類の1回分）ごとに、AI呼び出しをすべて終えてから分類・本文の書き込みを
    一括でコミットする。分類結果だけが確定して本文統合が漏れると、報告が分類済みとして二度と
    統合されないため（CODING_RULES.md「AI通信とトランザクション」）。途中で失敗したチャンクは
    取り消され、未分類のまま次回のバッチで再処理される。
    """
    entries = recap_service.collect_pending_entries(
        session, goal, goal.start_date, today - dt.timedelta(days=1)
    )
    texts = [t for t in recap_service.entry_texts(session, entries) if t.text.strip()]
    chunk_budget = setting_reader.get_int(session, RECAP_CLASSIFY_CHUNK_CHARS)
    classified = 0
    for chunk in _chunk_by_chars(texts, chunk_budget):
        response = _send(
            session,
            goal,
            AiPurpose.RECAP_CLASSIFY,
            {
                "existing_themes": _existing_theme_lines(session, goal),
                "entries": "\n".join(f"#{t.entry_id}（{t.record_date}）: {t.text}" for t in chunk),
            },
            scope_key=f"classify-{today.isoformat()}",
        )
        classification = recap_service.parse_classification(response, {t.entry_id for t in chunk})
        bodies = _compose_theme_bodies(session, goal, classification, chunk)
        recap_service.apply_classification(session, goal, classification)
        _apply_theme_bodies(session, goal, bodies)
        session.commit()
        classified += len(classification)
    return classified


def _chunk_by_chars(texts: list[recap_service.EntryText], budget: int):
    """報告本文を、合計文字数が予算を超えないよう順に区切る（1件が予算を超える場合は単独）。"""
    chunk: list[recap_service.EntryText] = []
    size = 0
    for item in texts:
        if chunk and size + len(item.text) > budget:
            yield chunk
            chunk, size = [], 0
        chunk.append(item)
        size += len(item.text)
    if chunk:
        yield chunk


def _existing_theme_lines(session: Session, goal: Goal) -> str:
    names = session.scalars(
        select(RecapTheme.name).where(RecapTheme.goal_id == goal.id).order_by(RecapTheme.name)
    ).all()
    return "\n".join(f"- {name}" for name in names) or RECAP_NO_THEMES_PLACEHOLDER


def _compose_theme_bodies(
    session: Session,
    goal: Goal,
    classification: dict[int, list[str]],
    chunk: list[recap_service.EntryText],
) -> dict[str, str]:
    """今回の分類で関連付いた報告を、テーマごとに統合した新しい本文を組み立てる（テーマ名→本文）。

    AI呼び出しだけを行い、テーマや本文の書き込みはしない（書き込みは呼び出し元が分類と
    まとめて行う）。未作成のテーマは本文が空で、会話はテーマ名で識別する（まだIDが無いため）。
    """
    text_by_id = {t.entry_id: t for t in chunk}
    items_by_name: dict[str, list[recap_service.EntryText]] = defaultdict(list)
    for entry_id, names in classification.items():
        for name in names:
            items_by_name[name].append(text_by_id[entry_id])
    themes_by_name = {
        theme.name: theme
        for theme in session.scalars(
            select(RecapTheme).where(
                RecapTheme.goal_id == goal.id, RecapTheme.name.in_(list(items_by_name))
            )
        ).all()
    }
    bodies: dict[str, str] = {}
    for name, items in items_by_name.items():
        theme = themes_by_name.get(name)
        if theme is None:
            bodies[name] = _next_body(session, goal, name, f"theme-name-{name}", "", items)
        else:
            bodies[name] = _next_body(session, goal, name, f"theme-{theme.id}", theme.body, items)
    return bodies


def _apply_theme_bodies(session: Session, goal: Goal, bodies: dict[str, str]) -> None:
    """組み立て済みの本文を、テーマ名で対応するテーマへ反映する（分類の反映後に呼ぶ）。"""
    if not bodies:
        return
    for theme in session.scalars(
        select(RecapTheme).where(RecapTheme.goal_id == goal.id, RecapTheme.name.in_(list(bodies)))
    ).all():
        theme.body = bodies[theme.name]


def rebuild_theme(session: Session, goal: Goal, theme: RecapTheme) -> None:
    """テーマの本文を、紐付く報告の原文から作り直す（利用者の「再構築」操作）。

    既存の本文は、全チャンクの統合が成功した後にだけ置き換える。途中で採用されない応答が
    あれば例外で中止し、本文は変更されない。報告が1件も無い場合は何もしない。
    """
    texts = [
        t
        for t in recap_service.entry_texts(session, recap_service.theme_entry_rows(session, theme))
        if t.text.strip()
    ]
    if not texts:
        return
    budget = setting_reader.get_int(session, RECAP_CLASSIFY_CHUNK_CHARS)
    body = ""
    for chunk in _chunk_by_chars(texts, budget):
        body = _next_body(session, goal, theme.name, f"theme-{theme.id}", body, chunk)
    theme.body = body


def _next_body(
    session: Session,
    goal: Goal,
    theme_name: str,
    scope_key: str,
    current_body: str,
    new_items: list[recap_service.EntryText],
) -> str:
    """テーマ本文の統合結果をAIから得る（書き込みはしない。呼び出し元が確定させる）。"""
    body_max = setting_reader.get_int(session, RECAP_BODY_MAX_CHARS)
    retention = setting_reader.get_float(session, RECAP_MIN_RETENTION_RATIO)
    response = _send(
        session,
        goal,
        AiPurpose.RECAP_THEME_BODY,
        {
            "theme_name": theme_name,
            "current_body": current_body or RECAP_BODY_EMPTY_PLACEHOLDER,
            "new_entries": "\n".join(f"（{t.record_date}）{t.text}" for t in new_items),
            "body_max_chars": str(body_max),
        },
        scope_key=scope_key,
    ).strip()
    if not response:
        raise RecapBodyRejectedError(f"empty theme body: {theme_name}")
    if current_body and len(response) < len(current_body) * retention:
        raise RecapBodyRejectedError(f"theme body shrank below retention: {theme_name}")
    return response


def _send(
    session: Session,
    goal: Goal,
    purpose: AiPurpose,
    variables: dict[str, str],
    *,
    scope_key: str,
) -> str:
    template_body = ai_orchestration.load_template_body(session, purpose)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    built = prompt_builder.build_simple(template_body, variables, max_chars)
    if built.was_truncated:
        raise RecapPromptTooLongError(f"prompt exceeds the limit: {purpose}")
    assistant_uid = setting_reader.get_str(session, _ASSISTANT_KEY_BY_CATEGORY[goal.category])
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.RECAP,
        scope_key=scope_key,
        assistant_uid=assistant_uid,
        title=f"{RECAP_CONVERSATION_TITLE_PREFIX} {scope_key}",
    )
    result = ai_orchestration.send_and_log(
        session,
        purpose=purpose,
        conversation=conversation,
        prompt_text=built.text,
        prompt_chars=built.prompt_chars,
        was_truncated=built.was_truncated,
    )
    return result.response_text


def run_all(session: Session, today: dt.date) -> int:
    """資格試験・読書の進行中の目標すべてについて振り返りを更新する（起動時バッチ）。

    1件の失敗が他の目標を止めないよう、目標ごとに取り消して続行する（16.7）。
    戻り値は分類できた報告の総件数。
    """
    goals = ai_context_service.list_active_exam_goals(
        session
    ) + ai_context_service.list_active_reading_goals(session)
    total = 0
    for goal in goals:
        try:
            total += run_for_goal(session, goal, today)
            session.commit()
        except Exception:  # noqa: BLE001 - 1件の失敗で起動時処理全体を止めないため意図的に握りつぶす
            session.rollback()
    return total
