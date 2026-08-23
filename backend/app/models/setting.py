"""設定系モデル（設計書 データ構造編 5.2）。"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AppSettingValueType, DayType
from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin, utcnow


class AppSetting(UpdatedAtMixin, Base):
    """設定のキーバリュー。閾値・パラメータはここへ外部化する（直接記述禁止）。"""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[AppSettingValueType] = mapped_column(
        Enum(AppSettingValueType, native_enum=False, validate_strings=True), nullable=False
    )


class PromptTemplate(UpdatedAtMixin, Base):
    """AIプロンプトのテンプレート。文面はここへ外部化する（直接記述禁止）。"""

    __tablename__ = "prompt_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Holiday(Base):
    """祝日（内閣府CSVの手動インポート）。"""

    __tablename__ = "holiday"

    holiday_date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DayTypeDefault(Base):
    """曜日別の日種別既定値。0=月曜〜6=日曜。OFFは既定値に設定できない（サービス層で検証）。"""

    __tablename__ = "day_type_default"

    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_type: Mapped[DayType] = mapped_column(
        Enum(DayType, native_enum=False, validate_strings=True), nullable=False
    )


class CalendarDayOverride(CreatedAtMixin, Base):
    """日付単位の日種別上書き。"""

    __tablename__ = "calendar_day_override"

    target_date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_type: Mapped[DayType] = mapped_column(
        Enum(DayType, native_enum=False, validate_strings=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
