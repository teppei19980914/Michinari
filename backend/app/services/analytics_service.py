"""分析画面固有の算出（仕様書6.8 SC-09、データ構造編8章、実装フェーズ分割計画書Phase9）。

cycle_service・metrics_service・speed_service・baseline_service等、既存章の算出ロジックは
それぞれの担当ファイルに置く（12〜14章）。本ファイルには、それらのどの章にも属さない
分析画面固有の算出（計画線・成長記述の抽出）のみを置く。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose, ChatRole, DayType, GoalCategory
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage, DailyRecord, ReadingLog, WorkLog
from app.models.work import WorkAssignment
from app.services import calendar_service
from app.services.cycle_service import ProgressPoint
from app.services.exceptions import NotFoundError, ValidationError

#: 成長記述タブ（日次フィードバックのAI応答）のカテゴリとpurposeの対応（Phase26）。
_GROWTH_DESCRIPTION_PURPOSE_BY_CATEGORY = {
    GoalCategory.EXAM: AiPurpose.DAILY_FEEDBACK,
    GoalCategory.READING: AiPurpose.DAILY_FEEDBACK_READING,
    GoalCategory.WORK: AiPurpose.DAILY_FEEDBACK_WORK,
}
#: 上記の逆引き（purpose→category）。assign_growth_description_goalが、成長記述と無関係な
#: purpose（週次要約・総括レポート等）のメッセージを渡された場合に安全にNoneを返せるよう
#: dict.get()で参照できる形にする（Phase26レビューで発見、next()のStopIteration回避）。
_GROWTH_DESCRIPTION_PURPOSE_BY_CATEGORY_REVERSE = {
    purpose: category for category, purpose in _GROWTH_DESCRIPTION_PURPOSE_BY_CATEGORY.items()
}


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
    """成長記述タブの1件（仕様書6.8「AIによる過去記述との比較結果の履歴」、ANL-07）。

    message_id・goal_id はPhase26で追加した。goal_id が None のエントリは、目標単位分離
    （chat_message.goal_id追加）より前に生成されたレガシーメッセージで、どの目標宛てか
    技術的に判別不能なため「未割り当て」として扱う（分析タブ上で利用者が手動で割り当てる）。
    """

    message_id: int
    record_date: dt.date
    content: str
    goal_id: int | None


def list_growth_descriptions(session: Session, goal: Goal) -> list[GrowthDescriptionEntry]:
    """指定した目標宛ての日次報告フィードバック応答を日付順（新しい順）に列挙する。

    データ構造編8章のエンドポイント一覧（/analytics/quality・progress・forecast・speed・
    gantt）には成長記述タブ用のエンドポイントが明記されていないが、仕様書6.8で7タブ構成の
    1つ（ANL-07、MVP）として必須のため、Phase9実装判断として追加した。

    Phase26で日次フィードバックのAI対話を目標単位の会話へ分離し（未決事項L-07の解消方針
    転換）、本関数もgoal_idで絞り込む方式に変更した。goal.categoryに対応するpurposeの
    レガシーメッセージ（goal_id=NULL、移行前に生成されたため目標が未確定）も「未割り当て」
    として合わせて返し、利用者が分析タブ上で目標を手動で割り当てられるようにする
    （assign_growth_description_goal参照）。

    構造化された「成長の指摘」欄のみを抽出することはしない。抽出見出し文言（例:
    「## 2. 成長の指摘」）はprompt_templateテーブルの内容であり画面から編集可能なため、
    それに依存した文字列パースはハルシネーション・仕様不一致の原因になり得るためである。
    """
    purpose = _GROWTH_DESCRIPTION_PURPOSE_BY_CATEGORY[goal.category]
    rows = (
        session.query(
            ChatMessage.id, DailyRecord.record_date, ChatMessage.content, ChatMessage.goal_id
        )
        .join(ChatMessage, ChatMessage.daily_record_id == DailyRecord.id)
        .filter(
            ChatMessage.role == ChatRole.ASSISTANT,
            or_(
                ChatMessage.goal_id == goal.id,
                (ChatMessage.goal_id.is_(None)) & (ChatMessage.purpose == purpose),
            ),
        )
        .order_by(DailyRecord.record_date.desc(), ChatMessage.sequence.desc())
        .all()
    )
    return [
        GrowthDescriptionEntry(
            message_id=row[0], record_date=row[1], content=row[2], goal_id=row[3]
        )
        for row in rows
    ]


def assign_growth_description_goal(session: Session, message: ChatMessage, goal: Goal) -> None:
    """未割り当ての成長記述（chat_message.goal_id=NULL）に目標を手動で割り当てる（Phase26）。

    移行前のレガシーメッセージはどの目標宛てか技術的に判別不能なため、利用者が分析タブ上の
    プルダウンから記憶を頼りに割り当てる（データの再生成は行わず、goal_id列の更新のみ）。
    メッセージのpurpose（DAILY_FEEDBACK等）に対応するカテゴリと異なる目標は割り当てられない
    （例: 読書の想起記録の対話を資格試験目標に割り当てることはできない）。既に割り当て済み
    （goal_id が非NULL）のメッセージは対象外とする（誤操作による付け替え防止）。
    """
    if message.goal_id is not None:
        raise ValidationError("既に目標が割り当て済みの成長記述です")
    expected_category = _GROWTH_DESCRIPTION_PURPOSE_BY_CATEGORY_REVERSE.get(message.purpose)
    if expected_category is None:
        raise ValidationError("成長記述として目標を割り当てられないメッセージです")
    if goal.category != expected_category:
        raise ValidationError(
            f"このメッセージは{expected_category.value}カテゴリの目標にのみ割り当てられます"
        )
    message.goal_id = goal.id
    session.flush()


def get_chat_message(session: Session, message_id: int) -> ChatMessage:
    message = session.get(ChatMessage, message_id)
    if message is None:
        raise NotFoundError("AI対話メッセージ", message_id)
    return message


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
