"""週次要約の生成判定と遡及実行（設計書 ロジック・プロンプト編15章・17.3・17.11・17.12、
データ構造編5.5、実装フェーズ分割計画書Phase5、L-11）。

アプリケーション起動時に評価し、完了しているが未生成の週を遡及生成する（15.2）。
実運用でのAI呼び出しを伴うため、実サーバ起動（app/main.py の __main__ ブロック）から
のみ呼び出す。1件の生成失敗が他の週・目標の生成を妨げないよう、失敗はai_logへ記録して
継続する（16.7「AI呼び出しの失敗により実績入力の内容が失われてはならない」と同じ考え方で、
週次要約生成の失敗が起動そのものを妨げないようにする）。

L-11で読書・仕事にも週次要約を新設した際、資格試験専用だった実装をカテゴリ別の差分
（_CategorySpec）を注入する形に一般化した。goal_id・週の一意性で貫くAPI形状（PendingWeek・
WeeklySummary）自体はカテゴリを問わず共通のため、weekly_summaryテーブルもスキーマ変更なく
そのまま共用する（データ構造編5.5）。

G3（2026-10-18）：遡及対象の検索窓を固定の週数（旧summary.lookback_weeks）で打ち切る方式は、
その週数を超えてアプリを起動しなかった期間の週がその後も永久に要約されない不具合があった。
検索範囲は目標ごとの実質開始日（_CategorySpec.effective_start_date。読書はbook.start_date）
まで広げ、代わりに1回の起動で生成する件数の上限（summary.retroactive_max_per_run）で
起動時間の肥大化を抑える。新しい週を優先して生成し、上限を超えた古い週は次回以降の起動へ
回す（新しい週ほど日次報告フィードバックへの圧縮効果が大きいため）。

検索範囲を目標開始日まで広げたことで対象週数が無制限に増えうるため、週ごとにクエリを
発行する実装（週数に比例してクエリ数が増え、生成済みの古い週も起動ごとに再スキャンする）
は採用しない。`list_pending_weeks`はカテゴリ別に範囲一括の問い合わせ（_xxx_goal_ids_with_logs_by_week）
を1回ずつ行い、Python側で週ごとに振り分ける方式とし、クエリ数を対象週数に関係なく
一定（カテゴリ数＋2回）に保つ。
"""

import datetime as dt
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
    SUMMARY_RETROACTIVE_MAX_PER_RUN,
)
from app.constants.enums import AiPurpose, ConversationScope, GoalCategory
from app.models.base import utcnow
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, ReadingLog, StudyLog, WeeklySummary, WorkLog
from app.models.work import WorkAssignment
from app.services import (
    ai_context_common,
    ai_context_exam,
    ai_context_reading,
    ai_context_work,
    goal_service,
    setting_reader,
)

_logger = logging.getLogger(__name__)

#: 曜日番号（Python標準のweekday(): 月曜=0〜日曜=6）における週の終了曜日（15.1「日曜日を終了日」）。
_WEEK_END_WEEKDAY = 6


@dataclass(frozen=True)
class PendingWeek:
    goal: Goal
    week_start: dt.date
    week_end: dt.date


@dataclass(frozen=True)
class _CategorySpec:
    """週次要約のカテゴリ別差分（L-11）。goal.categoryごとに、対象goal_idの判定方法・
    AI用途・{{...}}変数の組み立て方だけが異なり、それ以外（週の判定・重複防止・保存先・
    起動時の遡及生成手順）は共通のためここへ集約する（CLAUDE.md DRYの原則）。
    """

    goal_category: GoalCategory
    purpose: AiPurpose
    scope: ConversationScope
    assistant_uid_key: str
    #: [range_start, range_end]内の実績から、週開始日（月曜）ごとにログがあるgoal_id集合を
    #: 返す（15.2手順3のカテゴリ別実装、G3で範囲一括問い合わせへ変更）。
    goal_ids_with_logs_by_week: Callable[[Session, dt.date, dt.date], dict[dt.date, set[int]]]
    #: {{week_range}}・{{anonymize}}以外の、カテゴリ固有の注入変数を組み立てる。
    build_variables: Callable[[Session, Goal, dt.date, dt.date], dict[str, str]]
    #: 遡及対象を広げる基準となる実質開始日（G3）。資格試験・仕事はgoal.start_date、
    #: 読書はgoal.start_dateとは独立に変更できるbook.start_dateを用いる（L-12と同じ区別）。
    effective_start_date: Callable[[Session, Goal], dt.date]


def _week_start_of(log_date: dt.date) -> dt.date:
    """ログの日付が属する週の開始日（月曜）を返す（15.1「月曜日を週の開始日」）。"""
    return log_date - dt.timedelta(days=log_date.weekday())


def _bucket_goal_ids_by_week(rows: Iterable[tuple[int, dt.date]]) -> dict[dt.date, set[int]]:
    """(goal_id, ログの日付)の行を週開始日単位のgoal_id集合へ振り分ける（G3の範囲一括問い合わせ
    で、カテゴリごとのクエリ関数から共通して使う）。"""
    buckets: dict[dt.date, set[int]] = {}
    for goal_id, log_date in rows:
        buckets.setdefault(_week_start_of(log_date), set()).add(goal_id)
    return buckets


def _exam_goal_ids_with_logs_by_week(
    session: Session, range_start: dt.date, range_end: dt.date
) -> dict[dt.date, set[int]]:
    rows = (
        session.query(Material.goal_id, DailyRecord.record_date)
        .join(StudyLog, StudyLog.material_id == Material.id)
        .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
        .filter(DailyRecord.record_date >= range_start, DailyRecord.record_date <= range_end)
        .distinct()
    )
    return _bucket_goal_ids_by_week(rows)


def _exam_week_variables(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> dict[str, str]:
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    return {
        "goal_name": goal.name,
        "week_logs": ai_context_exam.build_week_logs_text(session, goal, week_start, week_end),
        "week_metrics": ai_context_exam.build_week_metrics_text(
            session, goal, week_start, week_end, treat_holiday_as_buffer
        ),
        "week_diaries": ai_context_exam.build_week_diaries_text(
            session, goal, week_start, week_end
        ),
    }


def _reading_goal_ids_with_logs_by_week(
    session: Session, range_start: dt.date, range_end: dt.date
) -> dict[dt.date, set[int]]:
    rows = (
        session.query(Book.goal_id, DailyRecord.record_date)
        .join(ReadingLog, ReadingLog.book_id == Book.id)
        .join(DailyRecord, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(DailyRecord.record_date >= range_start, DailyRecord.record_date <= range_end)
        .distinct()
    )
    return _bucket_goal_ids_by_week(rows)


def _reading_week_variables(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> dict[str, str]:
    book = goal.book
    return {
        "book_title": book.title,
        "week_recalls": ai_context_reading.build_week_recalls_text(
            session, book, week_start, week_end
        ),
    }


def _work_goal_ids_with_logs_by_week(
    session: Session, range_start: dt.date, range_end: dt.date
) -> dict[dt.date, set[int]]:
    rows = (
        session.query(WorkAssignment.goal_id, DailyRecord.record_date)
        .join(WorkLog, WorkLog.work_assignment_id == WorkAssignment.id)
        .join(DailyRecord, WorkLog.daily_record_id == DailyRecord.id)
        .filter(DailyRecord.record_date >= range_start, DailyRecord.record_date <= range_end)
        .distinct()
    )
    return _bucket_goal_ids_by_week(rows)


def _work_week_variables(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> dict[str, str]:
    work_assignment = goal.work_assignment
    return {
        "work_name": goal.name,
        "week_logs": ai_context_work.build_week_work_logs_text(
            session, work_assignment, week_start, week_end
        ),
    }


_EXAM_SPEC = _CategorySpec(
    goal_category=GoalCategory.EXAM,
    purpose=AiPurpose.WEEKLY_SUMMARY,
    scope=ConversationScope.WEEKLY_SUMMARY,
    assistant_uid_key=AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    goal_ids_with_logs_by_week=_exam_goal_ids_with_logs_by_week,
    build_variables=_exam_week_variables,
    effective_start_date=lambda _session, goal: goal.start_date,
)
_READING_SPEC = _CategorySpec(
    goal_category=GoalCategory.READING,
    purpose=AiPurpose.WEEKLY_SUMMARY_READING,
    scope=ConversationScope.WEEKLY_SUMMARY_READING,
    assistant_uid_key=AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    goal_ids_with_logs_by_week=_reading_goal_ids_with_logs_by_week,
    build_variables=_reading_week_variables,
    effective_start_date=lambda _session, goal: goal.book.start_date,
)
_WORK_SPEC = _CategorySpec(
    goal_category=GoalCategory.WORK,
    purpose=AiPurpose.WEEKLY_SUMMARY_WORK,
    scope=ConversationScope.WEEKLY_SUMMARY_WORK,
    assistant_uid_key=AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
    goal_ids_with_logs_by_week=_work_goal_ids_with_logs_by_week,
    build_variables=_work_week_variables,
    effective_start_date=lambda _session, goal: goal.start_date,
)
_SPECS = (_EXAM_SPEC, _READING_SPEC, _WORK_SPEC)
_SPEC_BY_CATEGORY = {spec.goal_category: spec for spec in _SPECS}


def _last_completed_sunday(today: dt.date) -> dt.date:
    """T以前で最も近い日曜日を返す（15.2手順1。Tが日曜ならT自身）。"""
    offset = (today.weekday() - _WEEK_END_WEEKDAY) % 7
    return today - dt.timedelta(days=offset)


def _earliest_effective_start_date(session: Session) -> dt.date | None:
    """全目標のうち最も早い実質開始日を返す（G3。読書はbook.start_date）。
    目標が1件も無ければNoneを返す（遡及対象なし）。"""
    earliest: dt.date | None = None
    for spec in _SPECS:
        goals = session.query(Goal).filter(Goal.category == spec.goal_category).all()
        for goal in goals:
            start = spec.effective_start_date(session, goal)
            if earliest is None or start < earliest:
                earliest = start
    return earliest


def list_pending_weeks(session: Session, today: dt.date) -> list[PendingWeek]:
    """完了しているが未生成の(goal, week)組を列挙する（15.2手順1〜3、3カテゴリ横断）。

    遡及対象は固定の週数ではなく、全目標中最も早い実質開始日の週まで広げる（G3）。
    戻り値は新しい週が先頭（直近週→過去週の順）。1回の起動で生成する件数の絞り込みは
    呼び出し側（run_retroactive_generation）が担う。

    対象週数は目標開始日まで遡るため無制限に増えうる一方、問い合わせ件数は週数に
    関係なく一定（カテゴリ数＋2回）に保つ。週ごとにクエリを発行すると、既に生成済みの
    古い週も起動のたびに際限なく再スキャンすることになるため（G3是正時の性能レビューで
    指摘）、範囲全体を一括取得してからPython側で週ごとに振り分ける。
    """
    last_sunday = _last_completed_sunday(today)
    earliest_start = _earliest_effective_start_date(session)
    if earliest_start is None:
        return []
    earliest_week_start = _week_start_of(earliest_start)
    last_week_start = last_sunday - dt.timedelta(days=6)
    if earliest_week_start > last_week_start:
        return []
    weeks_count = (last_week_start - earliest_week_start).days // 7 + 1

    goal_ids_by_week: dict[dt.date, set[int]] = {}
    for spec in _SPECS:
        for week_start, goal_ids in spec.goal_ids_with_logs_by_week(
            session, earliest_week_start, last_sunday
        ).items():
            goal_ids_by_week.setdefault(week_start, set()).update(goal_ids)
    if not goal_ids_by_week:
        return []

    all_goal_ids = {goal_id for ids in goal_ids_by_week.values() for goal_id in ids}
    already_generated_by_week: dict[dt.date, set[int]] = {}
    for goal_id, week_start_date in session.query(
        WeeklySummary.goal_id, WeeklySummary.week_start_date
    ).filter(
        WeeklySummary.goal_id.in_(all_goal_ids),
        WeeklySummary.week_start_date >= earliest_week_start,
        WeeklySummary.week_start_date <= last_week_start,
        WeeklySummary.is_anonymized.is_(False),
    ):
        already_generated_by_week.setdefault(week_start_date, set()).add(goal_id)
    goals_by_id = {
        goal.id: goal for goal in session.query(Goal).filter(Goal.id.in_(all_goal_ids)).all()
    }

    pending: list[PendingWeek] = []
    for offset in range(weeks_count):
        week_end = last_sunday - dt.timedelta(days=7 * offset)
        week_start = week_end - dt.timedelta(days=6)

        goal_ids_with_logs = goal_ids_by_week.get(week_start)
        if not goal_ids_with_logs:
            continue
        target_goal_ids = goal_ids_with_logs - already_generated_by_week.get(week_start, set())
        if not target_goal_ids:
            continue

        for goal_id in sorted(target_goal_ids):
            pending.append(
                PendingWeek(goal=goals_by_id[goal_id], week_start=week_start, week_end=week_end)
            )
    return pending


def invalidate_week(session: Session, goal: Goal, record_date: dt.date) -> None:
    """record_dateが属する週の既存の週次要約（匿名化版を含む）を削除し、未生成の状態に
    戻す（G4：完了週の実績・日記を事後に修正・新規登録しても、生成済みの週次要約が
    古いまま使われ続けてしまう不具合への対応）。

    新しいフラグ列を設けず「行が存在しない＝未生成」という既存の意味（list_pending_weeks
    の判定、15.2）をそのまま再利用する。削除するだけで次回起動時の遡及生成
    （run_retroactive_generation）が未生成週として拾い直す。対象週の要約がまだ無い場合
    （未完了週への入力時など）は0件削除となるだけで副作用はない。

    匿名化版も同時に削除するのは、非匿名化版だけを消すとregenerate_all_weekly_summaries_
    anonymizedが基準にする_non_anonymized_weeks_queryからこの週が外れ、古い匿名化版だけが
    更新されずエクスポートに出続けてしまうため（データ構造編7.3、開発Todo S06 D3・D4）。
    """
    week_start = _week_start_of(record_date)
    session.query(WeeklySummary).filter(
        WeeklySummary.goal_id == goal.id, WeeklySummary.week_start_date == week_start
    ).delete()


def invalidate_weeks(session: Session, goals: Iterable[Goal], record_date: dt.date) -> None:
    """複数件の実績・日記を1回の呼び出しで更新した場合に、目標ごとに重複なく
    invalidate_weekを呼ぶ（G4。CLAUDE.md パフォーマンスチェック：同一目標の教材・書籍・
    案件を複数件同時に更新しても、goal_id+week_start_dateが同じDELETEを件数分発行しない
    よう、呼び出し元の_apply_*_logs/_apply_diary_entriesがこちらを使う）。

    使用例（_apply_study_logsでの呼び方。goalsには重複・順不同で渡してよい）：
        invalidate_weeks(
            session, (m.goal for m in materials.values()), daily_record.record_date
        )
    """
    seen_goal_ids: set[int] = set()
    for goal in goals:
        if goal.id in seen_goal_ids:
            continue
        seen_goal_ids.add(goal.id)
        invalidate_week(session, goal, record_date)


def generate_for_week(
    session: Session,
    goal: Goal,
    week_start: dt.date,
    week_end: dt.date,
    *,
    anonymize: bool = False,
) -> WeeklySummary:
    """1件の(goal, week)について週次要約を生成する（17.3・17.11・17.12）。失敗時は例外を
    そのまま送出する（呼び出し側 run_retroactive_generation で1件ずつ捕捉し、他の生成を
    継続させる）。goal.categoryに応じた_CategorySpecで、AI用途・注入変数を切り替える（L-11）。

    anonymize=True の場合、匿名化版として別のAI会話（scope_keyを分離）で生成する
    （データ構造編7.3「匿名化版の週次要約は別レコードとして保持し、元の版は削除しない」）。
    既に匿名化版が存在する週の再エクスポートでは、そのレコードを最新内容へ更新する
    （goal_id・week_start_date・is_anonymizedの一意制約により重複作成できないため）。
    """
    spec = _SPEC_BY_CATEGORY[goal.category]
    variables = {
        "week_range": f"{week_start.isoformat()}〜{week_end.isoformat()}",
        **spec.build_variables(session, goal, week_start, week_end),
        "anonymize": ai_context_common.build_anonymize_instruction(anonymize),
    }

    template_body = ai_orchestration.load_template_body(session, spec.purpose)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, spec.assistant_uid_key)
    scope_key = f"{week_start.isoformat()}_anon" if anonymize else week_start.isoformat()
    title = f"{week_start.isoformat()}週 週次要約" + ("（匿名化）" if anonymize else "")
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=spec.scope,
        scope_key=scope_key,
        assistant_uid=assistant_uid,
        title=title,
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=spec.purpose,
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


def _non_anonymized_weeks_query(session: Session, goal: Goal):
    return (
        session.query(WeeklySummary.week_start_date, WeeklySummary.week_end_date)
        .filter(WeeklySummary.goal_id == goal.id, WeeklySummary.is_anonymized.is_(False))
        .order_by(WeeklySummary.week_start_date)
    )


def count_pending_anonymization_weeks(session: Session, goal: Goal) -> int:
    """匿名化がまだ生成されていない週次要約の件数を返す（進捗表示の合計値算出用、
    実装フェーズ分割計画書Phase10注意点）。"""
    return _non_anonymized_weeks_query(session, goal).count()


def regenerate_all_weekly_summaries_anonymized(
    session: Session, goal: Goal, *, on_progress: Callable[[], None] | None = None
) -> int:
    """目標の全週の週次要約について、匿名化版を（再）生成する（データ構造編7.3、
    実装フェーズ分割計画書Phase10注意点「匿名化時の再生成は複数回のAI呼び出しを伴う。
    呼び出し間隔の下限を守り、進捗を表示すること」）。

    run_retroactive_generationと異なり、1件でも失敗したら例外をそのまま送出して処理全体を
    中断する。匿名化はセンシティブな記述を除去するための操作であり、一部の週だけ非匿名の
    元記述が残ったままエクスポートされることは情報漏洩のリスクとなるため、
    run_retroactive_generationの「1件の失敗を握りつぶして継続する」方針（16.7）を
    ここでは意図的に採用しない。

    on_progress は1件生成するたびに呼び出す通知コールバックで、呼び出し元（export_service_common）が
    進捗表示（app.services.export_progress）へ反映するために用いる。
    """
    weeks = _non_anonymized_weeks_query(session, goal).all()
    count = 0
    for week_start, week_end in weeks:
        generate_for_week(session, goal, week_start, week_end, anonymize=True)
        count += 1
        if on_progress is not None:
            on_progress()
    return count


def run_retroactive_generation(session: Session, today: dt.date) -> int:
    """起動時の遡及生成（15.2手順4：呼び出し間隔の下限を守って逐次実行する）。

    1件の失敗が他の生成を妨げないよう、goal・週ごとに例外を捕捉して次へ進む
    （16.7の考え方を起動時処理にも適用）。AI呼び出し自体の失敗はgenerate_for_week内で
    既にcommit済み（ai_logのエラー記録を残すため）なので、ここでのrollbackは
    generate_for_week内のtry/except到達前に起きた想定外の例外に対する保険。
    戻り値は実際に生成できた件数。

    遡及対象は目標開始日まで広がる（G3）ため、1回の起動で生成する件数を
    summary.retroactive_max_per_runで区切る。list_pending_weeksは新しい週が先頭の順で
    返すため、先頭から上限件数だけを対象にすれば新しい週から生成される。上限を超えた
    古い週は次回以降の起動で引き続き未生成のまま列挙され、生成される。
    """
    max_per_run = setting_reader.get_int(session, SUMMARY_RETROACTIVE_MAX_PER_RUN)
    pending = list_pending_weeks(session, today)[:max_per_run]
    generated = 0
    for item in pending:
        try:
            generate_for_week(session, item.goal, item.week_start, item.week_end)
            session.commit()
            generated += 1
        except Exception:  # noqa: BLE001 - 1件の失敗で起動処理全体を止めないため意図的に握りつぶす
            # 画面には出ないため、原因を追えるようログに残す（次回起動で再試行される）。
            _logger.exception(
                "週次要約の遡及生成に失敗しました: goal_id=%s week_start=%s",
                item.goal.id,
                item.week_start,
            )
            session.rollback()
    return generated
