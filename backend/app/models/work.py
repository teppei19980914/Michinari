"""案件情報モデル（設計書 データ構造編 5.3「work_assignment（案件情報）」）。

category=WORKのgoalに対し、exam_subjectとmaterialを統合した位置づけの
子テーブルとして1件登録する（goal_idにUNIQUE制約＝1目標1案件、要件定義書R-72）。
bookと異なりdue_dateは持たない（仕事の案件は納期未定のことが多く、読書の読了目標日
のような必須の外部制約が存在しないため。要件定義書R-73）。
案件の終了（成果あり／なし）はgoal.statusで表現するため、独自のstatus/completed_at
は持たない。
"""

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import WorkEvaluationRole, WorkMemberGender
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal
    from app.models.record import WorkLog


class WorkAssignment(TimestampMixin, Base):
    """案件情報。expected_contentは登録後も更新可能で、更新は上書き（変更履歴なし）。"""

    __tablename__ = "work_assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    client_name: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_content: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # 利用者自身の自己申告ロール（要件定義書6.11）。マルチユーザー機能ではなく単独利用の
    # 利用者がこの案件に対しどちらの立場かを自己申告する1フィールド（nullable、デフォルトなし）。
    role: Mapped[WorkEvaluationRole | None] = mapped_column(
        Enum(WorkEvaluationRole, native_enum=False, validate_strings=True), nullable=True
    )

    goal: Mapped["Goal"] = relationship(back_populates="work_assignment")
    # work_assignment -> work_log は RESTRICT（業務記録が残る案件は削除不可、book/material
    # と同じ方針。データ構造編5.3）。
    work_logs: Mapped[list["WorkLog"]] = relationship(
        back_populates="work_assignment", passive_deletes=True
    )
    members: Mapped[list["WorkMember"]] = relationship(
        back_populates="work_assignment", passive_deletes=True
    )
    evaluation_reports: Mapped[list["WorkEvaluationReport"]] = relationship(
        back_populates="work_assignment", passive_deletes=True
    )


class WorkMember(TimestampMixin, Base):
    """チームメンバー（要件定義書6.11「チームメンバー管理」）。work_assignmentの子
    （book/materialがgoalの子であるのと同じ位置づけ）。

    characteristics（特徴・性格）は本アプリ初の第三者PIIフィールドであり、
    consent_confirmed_at（本人確認済みの確認時刻）が設定されないまま非空の値を
    保存することはできない（work_member_service._apply_characteristics）。
    genderは任意項目で同意ゲートの対象外（要件定義書6.11で明示的にcharacteristicsのみと
    範囲確定）。

    is_activeによるソフトデリート（Material.is_activeと同じ方針）を採用し、物理削除
    （DELETE /work-members/{id}）は評価レポートが存在する場合に拒否する
    （WorkMemberHasEvaluationReportsError）。これにより、無効化後も過去の評価レポートが
    メンバー名を解決できる。
    """

    __tablename__ = "work_member"
    __table_args__ = (Index("ix_work_member_work_assignment_id", "work_assignment_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("work_assignment.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[WorkMemberGender | None] = mapped_column(
        Enum(WorkMemberGender, native_enum=False, validate_strings=True), nullable=True
    )
    characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    work_assignment: Mapped["WorkAssignment"] = relationship(back_populates="members")
    # work_member -> work_evaluation_report はondelete指定なし（RESTRICT相当）。
    # 評価レポートが存在するメンバーの物理削除はサービス層で拒否する（データ構造編6.2相当）。
    evaluation_reports: Mapped[list["WorkEvaluationReport"]] = relationship(back_populates="member")


class WorkEvaluationReport(TimestampMixin, Base):
    """AI評価レポート（要件定義書6.11）。goal_retrospective（月次報告・半期評価、
    grainは(goal_id, period_type, period_key)）とはgrainが異なる（メンバー軸）ため、
    流用せず新規テーブルとする。

    生成のたびに新規行を追加する履歴保持型（EXAM/READINGのgoal_retrospectiveと同型。
    WORKの月次/半期報告のような1期間1行upsertとは異なる＝メンバー評価は時系列の
    複数回生成に意味があるため）。生成後、月次/半期報告と同様に人がレビュー・修正して
    から保存する運用のため、edited_atを持つ（goal_retrospective.edited_atと同じ意味）。
    """

    __tablename__ = "work_evaluation_report"
    __table_args__ = (Index("ix_work_evaluation_report_member_id", "member_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("work_assignment.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("work_member.id"), nullable=False)
    considerations: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    edited_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    work_assignment: Mapped["WorkAssignment"] = relationship(back_populates="evaluation_reports")
    member: Mapped["WorkMember"] = relationship(back_populates="evaluation_reports")
