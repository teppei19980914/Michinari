"""教材系モデル（設計書 データ構造編 5.3）。

current_cycle は保存しない（累積完了量から導出する派生値のため）。
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import BaselineReason, Environment, QualityMetricType
from app.models.base import Base, CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import ExamSubject, Goal
    from app.models.record import StudyLog


class Material(TimestampMixin, Base):
    """教材。総作業量・現在周回は total_amount / planned_cycles / 実績から都度算出する。"""

    __tablename__ = "material"
    __table_args__ = (
        Index("ix_material_goal_id", "goal_id"),
        Index("ix_material_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    unit_label: Mapped[str] = mapped_column(String, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    planned_cycles: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required_block_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_environment: Mapped[Environment] = mapped_column(
        Enum(Environment, native_enum=False, validate_strings=True),
        nullable=False,
        default=Environment.ANY,
    )
    quality_metric_type: Mapped[QualityMetricType] = mapped_column(
        Enum(QualityMetricType, native_enum=False, validate_strings=True),
        nullable=False,
        default=QualityMetricType.NONE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="materials")
    subject_links: Mapped[list["MaterialSubject"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    plan_baselines: Mapped[list["PlanBaseline"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    # material -> study_log は RESTRICT（実績が残る教材は削除不可）。
    # ORM側では削除操作を持ち込まない（passive_deletes でDB制約に委ねる）。
    study_logs: Mapped[list["StudyLog"]] = relationship(
        back_populates="material", passive_deletes=True
    )


class MaterialSubject(Base):
    """教材と科目の紐付け。同一goal所属であることはサービス層で検証する。"""

    __tablename__ = "material_subject"
    __table_args__ = (Index("ix_material_subject_subject_id", "subject_id"),)

    material_id: Mapped[int] = mapped_column(
        ForeignKey("material.id", ondelete="CASCADE"), primary_key=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("exam_subject.id", ondelete="CASCADE"), primary_key=True
    )

    material: Mapped["Material"] = relationship(back_populates="subject_links")
    subject: Mapped["ExamSubject"] = relationship(back_populates="material_links")


class PlanBaseline(CreatedAtMixin, Base):
    """計画基準値。リプラン履歴・総括レポートの分析根拠となる。"""

    __tablename__ = "plan_baseline"
    __table_args__ = (
        Index("ix_plan_baseline_material_effective", "material_id", "effective_from"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("material.id", ondelete="CASCADE"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_daily_quota: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_at_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    plan_days_at_baseline: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_cycles_at_baseline: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[BaselineReason] = mapped_column(
        Enum(BaselineReason, native_enum=False, validate_strings=True), nullable=False
    )

    material: Mapped["Material"] = relationship(back_populates="plan_baselines")
