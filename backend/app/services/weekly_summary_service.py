"""週次要約の生成判定と遡及実行（設計書 ロジック・プロンプト編15章・17.3、
データ構造編5.5、実装フェーズ分割計画書Phase5）。

アプリケーション起動時に評価し、完了しているが未生成の週を遡及生成する（15.2）。
実運用でのAI呼び出しを伴うため、実サーバ起動（app/main.py の __main__ ブロック）から
のみ呼び出す。1件の生成失敗が他の週・目標の生成を妨げないよう、失敗はai_logへ記録して
継続する（16.7「AI呼び出しの失敗により実績入力の内容が失われてはならない」と同じ考え方で、
週次要約生成の失敗が起動そのものを妨げないようにする）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_WEEKLY_SUMMARY, SUMMARY_LOOKBACK_WEEKS
from app.constants.enums import AiPurpose, ConversationScope
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog, WeeklySummary
from app.services import ai_context_service, goal_service, setting_reader

#: 曜日番号（Python標準のweekday(): 月曜=0〜日曜=6）における週の終了曜日（15.1「日曜日を終了日」）。
_WEEK_END_WEEKDAY = 6


@dataclass(frozen=True)
class PendingWeek:
    goal: Goal
    week_start: dt.date
    week_end: dt.date


def _last_completed_sunday(today: dt.date) -> dt.date:
    """T以前で最も近い日曜日を返す（15.2手順1。Tが日曜ならT自身）。"""
    offset = (today.weekday() - _WEEK_END_WEEKDAY) % 7
    return today - dt.timedelta(days=offset)


def list_pending_weeks(session: Session, today: dt.date, lookback_weeks: int) -> list[PendingWeek]:
    """完了しているが未生成の(goal, week)組を列挙する（15.2手順1〜3）。"""
    last_sunday = _last_completed_sunday(today)
    pending: list[PendingWeek] = []
    for offset in range(lookback_weeks):
        week_end = last_sunday - dt.timedelta(days=7 * offset)
        week_start = week_end - dt.timedelta(days=6)

        goal_ids_with_logs = {
            row[0]
            for row in session.query(Material.goal_id)
            .join(StudyLog, StudyLog.material_id == Material.id)
            .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
            .filter(DailyRecord.record_date >= week_start, DailyRecord.record_date <= week_end)
            .distinct()
        }
        if not goal_ids_with_logs:
            continue

        already_generated = {
            row[0]
            for row in session.query(WeeklySummary.goal_id).filter(
                WeeklySummary.goal_id.in_(goal_ids_with_logs),
                WeeklySummary.week_start_date == week_start,
                WeeklySummary.is_anonymized.is_(False),
            )
        }
        target_goal_ids = goal_ids_with_logs - already_generated
        if not target_goal_ids:
            continue

        goals = session.query(Goal).filter(Goal.id.in_(target_goal_ids)).order_by(Goal.id).all()
        for goal in goals:
            pending.append(PendingWeek(goal=goal, week_start=week_start, week_end=week_end))
    return pending


def generate_for_week(
    session: Session,
    goal: Goal,
    week_start: dt.date,
    week_end: dt.date,
    *,
    anonymize: bool = False,
) -> WeeklySummary:
    """1件の(goal, week)について週次要約を生成する（17.3）。失敗時は例外をそのまま送出する
    （呼び出し側 run_retroactive_generation で1件ずつ捕捉し、他の生成を継続させる）。

    anonymize=True の場合、匿名化版として別のAI会話（scope_keyを分離）で生成する
    （データ構造編7.3「匿名化版の週次要約は別レコードとして保持し、元の版は削除しない」）。
    既に匿名化版が存在する週の再エクスポートでは、そのレコードを最新内容へ更新する
    （goal_id・week_start_date・is_anonymizedの一意制約により重複作成できないため）。
    """
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    variables = {
        "week_range": f"{week_start.isoformat()}〜{week_end.isoformat()}",
        "goal_name": goal.name,
        "week_logs": ai_context_service.build_week_logs_text(session, goal, week_start, week_end),
        "week_metrics": ai_context_service.build_week_metrics_text(
            session, goal, week_start, week_end, treat_holiday_as_buffer
        ),
        "week_diaries": ai_context_service.build_week_diaries_text(session, week_start, week_end),
        "anonymize": ai_context_service.build_anonymize_instruction(anonymize),
    }

    template_body = ai_orchestration.load_template_body(session, AiPurpose.WEEKLY_SUMMARY)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_WEEKLY_SUMMARY)
    scope_key = f"{week_start.isoformat()}_anon" if anonymize else week_start.isoformat()
    title = f"{week_start.isoformat()}週 週次要約" + ("（匿名化）" if anonymize else "")
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.WEEKLY_SUMMARY,
        scope_key=scope_key,
        assistant_uid=assistant_uid,
        title=title,
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.WEEKLY_SUMMARY,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    summary_body = send_result.response_text.strip()
    existing = (
        session.query(WeeklySummary)
        .filter_by(goal_id=goal.id, week_start_date=week_start, is_anonymized=True)
        .first()
        if anonymize
        else None
    )
    if existing is not None:
        existing.summary_body = summary_body
        existing.generated_at = utcnow()
        summary = existing
    else:
        summary = WeeklySummary(
            goal_id=goal.id,
            week_start_date=week_start,
            week_end_date=week_end,
            summary_body=summary_body,
            is_anonymized=anonymize,
        )
        session.add(summary)
    session.flush()
    return summary


def regenerate_all_weekly_summaries_anonymized(session: Session, goal: Goal) -> int:
    """目標の全週の週次要約について、匿名化版を（再）生成する（データ構造編7.3、
    実装フェーズ分割計画書Phase10注意点「匿名化時の再生成は複数回のAI呼び出しを伴う」）。

    run_retroactive_generationと異なり、1件でも失敗したら例外をそのまま送出して処理全体を
    中断する。匿名化はセンシティブな記述を除去するための操作であり、一部の週だけ非匿名の
    元記述が残ったままエクスポートされることは情報漏洩のリスクとなるため、
    run_retroactive_generationの「1件の失敗を握りつぶして継続する」方針（16.7）を
    ここでは意図的に採用しない。
    """
    weeks = (
        session.query(WeeklySummary.week_start_date, WeeklySummary.week_end_date)
        .filter(WeeklySummary.goal_id == goal.id, WeeklySummary.is_anonymized.is_(False))
        .order_by(WeeklySummary.week_start_date)
        .all()
    )
    count = 0
    for week_start, week_end in weeks:
        generate_for_week(session, goal, week_start, week_end, anonymize=True)
        count += 1
    return count


def run_retroactive_generation(session: Session, today: dt.date) -> int:
    """起動時の遡及生成（15.2手順4：呼び出し間隔の下限を守って逐次実行する）。

    1件の失敗が他の生成を妨げないよう、goal・週ごとに例外を捕捉して次へ進む
    （16.7の考え方を起動時処理にも適用）。AI呼び出し自体の失敗はgenerate_for_week内で
    既にcommit済み（ai_logのエラー記録を残すため）なので、ここでのrollbackは
    generate_for_week内のtry/except到達前に起きた想定外の例外に対する保険。
    戻り値は実際に生成できた件数。
    """
    lookback_weeks = setting_reader.get_int(session, SUMMARY_LOOKBACK_WEEKS)
    pending = list_pending_weeks(session, today, lookback_weeks)
    generated = 0
    for item in pending:
        try:
            generate_for_week(session, item.goal, item.week_start, item.week_end)
            session.commit()
            generated += 1
        except Exception:  # noqa: BLE001 - 1件の失敗で起動処理全体を止めないため意図的に握りつぶす
            session.rollback()
    return generated
