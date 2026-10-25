"""目標相談チャットの相談履歴（S10、開発Todo v1.1 V6〜V8）。

保存・一覧・削除だけを担う（質疑そのものの処理は`goal_consultation_service_common.py`）。
既存の`ai_log`（用途別、`log.retention_days`で自動削除・goal_id無し）とは別の目的
（運用監視 vs 利用者向け恒久履歴）であり、本サービスが重複ではない（開発Todo v1.1 V8）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import GoalConsultationAnswerStatus
from app.database import serialize_writes
from app.models.goal import Goal, GoalConsultationLog
from app.services.exceptions import NotFoundError

#: cited_dates・cited_weeksの区切り文字（複数件をスペース区切りの文字列として保持する。
#: JSON列の前例が本アプリに無いため、開発Todo v1.1 §0「比較」の決定どおり単純な文字列で
#: 持つ）。
_ITEM_SEPARATOR = " "
#: 週の開始日・終了日の区切り（ISO日付はハイフンを含むため、全角チルダ等と混同しない
#: 記号を使う）。
_WEEK_RANGE_SEPARATOR = "~"


def _serialize_dates(dates: tuple[dt.date, ...]) -> str:
    return _ITEM_SEPARATOR.join(d.isoformat() for d in dates)


def _serialize_weeks(weeks: tuple[tuple[dt.date, dt.date], ...]) -> str:
    return _ITEM_SEPARATOR.join(
        f"{start.isoformat()}{_WEEK_RANGE_SEPARATOR}{end.isoformat()}" for start, end in weeks
    )


def _deserialize_dates(raw: str) -> tuple[dt.date, ...]:
    if not raw:
        return ()
    return tuple(dt.date.fromisoformat(token) for token in raw.split(_ITEM_SEPARATOR))


def _deserialize_weeks(raw: str) -> tuple[tuple[dt.date, dt.date], ...]:
    if not raw:
        return ()
    weeks = []
    for token in raw.split(_ITEM_SEPARATOR):
        start, end = token.split(_WEEK_RANGE_SEPARATOR)
        weeks.append((dt.date.fromisoformat(start), dt.date.fromisoformat(end)))
    return tuple(weeks)


@dataclass(frozen=True)
class GoalConsultationLogEntry:
    """相談履歴の1件（画面の一覧表示用、API層でRead schemaへ変換する）。"""

    id: int
    conversation_id: int
    question: str
    answer_status: GoalConsultationAnswerStatus
    answer_body: str
    cited_dates: tuple[dt.date, ...]
    cited_weeks: tuple[tuple[dt.date, dt.date], ...]
    created_at: dt.datetime


def _to_entry(row: GoalConsultationLog) -> GoalConsultationLogEntry:
    return GoalConsultationLogEntry(
        id=row.id,
        conversation_id=row.conversation_id,
        question=row.question,
        answer_status=row.answer_status,
        answer_body=row.answer_body,
        cited_dates=_deserialize_dates(row.cited_dates),
        cited_weeks=_deserialize_weeks(row.cited_weeks),
        created_at=row.created_at,
    )


def save(
    session: Session,
    *,
    goal: Goal,
    conversation_id: int,
    question: str,
    answer_status: GoalConsultationAnswerStatus,
    answer_body: str,
    cited_dates: tuple[dt.date, ...],
    cited_weeks: tuple[tuple[dt.date, dt.date], ...],
) -> None:
    """質問・回答・根拠を保存する（ANSWERED・UNAVAILABLEの両方、開発Todo v1.1 V8）。

    スカラー値で受け取ることで、呼び出し元（`goal_consultation_service_common.
    GoalConsultationAnswer`）への依存を持たない（循環import回避。本サービスは
    保存・一覧・削除専用で、質疑の結果の型を知る必要が無いため）。

    AI通信（送信・後始末）がすべて終わった後に呼ぶ想定の短い書き込み区間のため、
    `serialize_writes()`で直列化する（CODING_RULES.md「AI通信とトランザクション」と
    同じ方針）。
    """
    with serialize_writes():
        session.add(
            GoalConsultationLog(
                goal_id=goal.id,
                conversation_id=conversation_id,
                question=question,
                answer_status=answer_status,
                answer_body=answer_body,
                cited_dates=_serialize_dates(cited_dates),
                cited_weeks=_serialize_weeks(cited_weeks),
            )
        )
        session.commit()


def list_recent_answered_for_conversation(
    session: Session, conversation_id: int, limit: int
) -> list[GoalConsultationLogEntry]:
    """会話継続（S11）でプロンプトへ含める直近往復を、古い順で返す。

    `ANSWERED`のみを対象にする（開発Todo v1.2 W2。`UNAVAILABLE`は本文が空か、禁止語検出・
    出力形式失敗等で表示できない内容のため、後続の質問の文脈として積む意味が無い）。
    まず新しい順に`limit`件取得し、古い順へ並べ替える（同時刻はid降順でタイブレーク、
    CODING_RULES.md「タイムスタンプでの並び替え」）。
    """
    rows = (
        session.query(GoalConsultationLog)
        .filter(
            GoalConsultationLog.conversation_id == conversation_id,
            GoalConsultationLog.answer_status == GoalConsultationAnswerStatus.ANSWERED,
        )
        .order_by(GoalConsultationLog.created_at.desc(), GoalConsultationLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_entry(row) for row in reversed(rows)]


def list_for_goal(session: Session, goal: Goal) -> list[GoalConsultationLogEntry]:
    """この目標の相談履歴を、作成日時の古い順（同時刻はid昇順でタイブレーク、
    CODING_RULES.md「タイムスタンプでの並び替え」）に返す。件数は実運用上少数のため
    ページングは設けない（開発Todo v1.1 V7、YAGNI）。
    """
    rows = (
        session.query(GoalConsultationLog)
        .filter(GoalConsultationLog.goal_id == goal.id)
        .order_by(GoalConsultationLog.created_at, GoalConsultationLog.id)
        .all()
    )
    return [_to_entry(row) for row in rows]


def delete(session: Session, goal: Goal, log_id: int) -> None:
    """相談履歴を1件削除する。`goal_id`が一致しない場合はNotFoundError
    （他目標の履歴を誤って・不正に削除できないようにする、開発Todo v1.1 §5）。"""
    row = (
        session.query(GoalConsultationLog)
        .filter(GoalConsultationLog.id == log_id, GoalConsultationLog.goal_id == goal.id)
        .first()
    )
    if row is None:
        raise NotFoundError("GoalConsultationLog", log_id)
    session.delete(row)
    session.flush()
