"""分析画面固有の算出（仕様書6.8 SC-09、データ構造編8章、実装フェーズ分割計画書Phase9）。

cycle_service・metrics_service・speed_service・baseline_service等、既存章の算出ロジックは
それぞれの担当ファイルに置く（12〜14章）。本ファイルには、それらのどの章にも属さない
分析画面固有の算出（計画線・成長記述の抽出）のみを置く。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import ChatRole, DayType
from app.models.book import Book
from app.models.material import Material
from app.models.record import ChatMessage, DailyRecord, ReadingLog, WorkLog
from app.models.work import WorkAssignment
from app.services import calendar_service
from app.services.cycle_service import ProgressPoint


def compute_plan_line(
    session: Session, material: Material, treat_holiday_as_buffer: bool
) -> list[ProgressPoint]:
    """計画線（進捗タブで実績と比較する目標到達ペース）を算出する。

    仕様書6.8・設計書のいずれにも計算式の明記がないため、Phase9実装判断として
    plan_baseline（12章、リプランの都度記録される1日あたりノルマ）をPLAN日に沿って
    積算する方式を採用した。baseline_daily_quotaはリプラン時点の目標ペースであり、
    threshold_service.check_warningも同じ値を「目標ペース」として警告判定に使っている
    （日々変動する負荷係数を含まない、計画としての基準値であるため）。
    """
    baselines = sorted(material.plan_baselines, key=lambda b: b.effective_from)
    if not baselines:
        return []

    day_types = calendar_service.resolve_day_types(
        session, material.start_date, material.due_date, treat_holiday_as_buffer
    )

    points: list[ProgressPoint] = []
    running_total = 0.0
    baseline_index = 0
    current_quota = 0.0
    current_date = material.start_date
    while current_date <= material.due_date:
        while (
            baseline_index < len(baselines)
            and baselines[baseline_index].effective_from <= current_date
        ):
            current_quota = baselines[baseline_index].baseline_daily_quota
            baseline_index += 1
        if day_types.get(current_date) == DayType.PLAN:
            running_total += current_quota
        points.append(ProgressPoint(record_date=current_date, cumulative_completed=running_total))
        current_date += dt.timedelta(days=1)
    return points


@dataclass(frozen=True)
class GrowthDescriptionEntry:
    """成長記述タブの1件（仕様書6.8「AIによる過去記述との比較結果の履歴」、ANL-07）。"""

    record_date: dt.date
    content: str


def list_growth_descriptions(session: Session) -> list[GrowthDescriptionEntry]:
    """AI日次報告フィードバックの応答を日付順（新しい順）に列挙する。

    データ構造編8章のエンドポイント一覧（/analytics/quality・progress・forecast・speed・
    gantt）には成長記述タブ用のエンドポイントが明記されていないが、仕様書6.8で7タブ構成の
    1つ（ANL-07、MVP）として必須のため、Phase9実装判断として追加した。

    「成長の指摘」はAI日次報告フィードバック（daily_feedback_service）の応答本文に含まれる
    自由記述であり、chat_messageは目標に紐付かない（daily_feedback_serviceが作成する
    ai_conversationはgoal_id=NULLで作成される、17.2「本日の記録」は当日ACTIVEな全目標を
    横断した内容のため）。したがって本タブは目標を横断した全件を返す。
    構造化された「成長の指摘」欄のみを抽出することはしない。抽出見出し文言（例:
    「## 2. 成長の指摘」）はprompt_templateテーブルの内容であり画面から編集可能なため、
    それに依存した文字列パースはハルシネーション・仕様不一致の原因になり得るためである。
    """
    rows = (
        session.query(DailyRecord.record_date, ChatMessage.content)
        .join(ChatMessage, ChatMessage.daily_record_id == DailyRecord.id)
        .filter(ChatMessage.role == ChatRole.ASSISTANT)
        .order_by(DailyRecord.record_date.desc(), ChatMessage.sequence.desc())
        .all()
    )
    return [GrowthDescriptionEntry(record_date=row[0], content=row[1]) for row in rows]


@dataclass(frozen=True)
class ReadingLogEntry:
    """分析画面「読書記録」タブの1件（読書目標category=READING向け、6.8補足）。

    資格試験の品質推移・進捗等5タブはMaterial（教材）に依存するため読書目標には
    適用できない。代わりに日々の想起記録（recall_body）を新しい順に列挙する
    （仕様書6.10「実績推移」の読書向け読み替え＝日別の想起記録一覧、と同じ発想）。
    """

    record_date: dt.date
    recall_body: str
    pages_read: int | None
    current_page: int | None


def list_reading_log_entries(session: Session, book: Book) -> list[ReadingLogEntry]:
    """bookに紐づく想起記録を、記録日の新しい順に全件列挙する。

    ai_context_service.build_reading_logs_textと結合条件（daily_record.id×book_id）が
    同一だが、あちらはAIプロンプト用にテキスト連結する用途、こちらは分析タブ表示用に
    構造化データのまま返す用途のため、戻り値の形が異なり関数を分けている。
    """
    rows = (
        session.query(
            DailyRecord.record_date,
            ReadingLog.recall_body,
            ReadingLog.pages_read,
            ReadingLog.current_page,
        )
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .order_by(DailyRecord.record_date.desc())
        .all()
    )
    return [
        ReadingLogEntry(
            record_date=row[0], recall_body=row[1], pages_read=row[2], current_page=row[3]
        )
        for row in rows
    ]


@dataclass(frozen=True)
class WorkLogEntry:
    """分析画面「業務記録」タブの1件（仕事目標category=WORK向け、6.8補足）。

    読書と同じ理由でMaterial非依存の一覧表示とする。日々の業務記録（body）を
    新しい順に列挙する（仕様書6.10「実績推移」の仕事向け読み替え＝日別の業務記録一覧）。
    """

    record_date: dt.date
    body: str


def list_work_log_entries(session: Session, work_assignment: WorkAssignment) -> list[WorkLogEntry]:
    """work_assignmentに紐づく業務記録を、記録日の新しい順に全件列挙する。

    ai_context_service.build_work_logs_text_for_periodと結合条件
    （daily_record.id×work_assignment_id）が同一だが、読書と同じ理由
    （list_reading_log_entries参照）で戻り値の形が異なるため関数を分けている。
    """
    rows = (
        session.query(DailyRecord.record_date, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(WorkLog.work_assignment_id == work_assignment.id)
        .order_by(DailyRecord.record_date.desc())
        .all()
    )
    return [WorkLogEntry(record_date=row[0], body=row[1]) for row in rows]
