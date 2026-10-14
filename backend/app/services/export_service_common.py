"""ナレッジエクスポート（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書Phase10）。

日記本文・AI対話履歴は仕様書6.10の出力項目選択に列挙されているが、データ構造編7.1の
JSONスキーマ例には対応するフィールドが無い（既定で除外される項目のため「概要」の例示に
含まれていないと解釈する）。選択された場合は7.1のスキーマを拡張し、"diaries"・
"ai_dialogue" キーを追加する（下記ExportSelectionのコメント参照）。

本モジュールは、目標の種類（資格試験・読書・仕事）を問わず2カテゴリ以上から参照される
共通処理を置く（実装フェーズ分割計画書S02、`export_service.py`からの分割）。カテゴリ固有の
処理は`export_service_exam.py`・`export_service_reading.py`・`export_service_work.py`に
分割して置く。
"""

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import EXPORT_DIR
from app.constants.enums import GoalCategory, RetrospectivePeriodType
from app.models.goal import Goal
from app.services import (
    export_progress,
    goal_service,
    retrospective_service,
    weekly_summary_service,
    work_report_service,
)

#: エクスポートファイル名に使えない文字を除去するための正規表現（目標名に含まれうる
#: ファイルシステム予約文字への対策）。
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

#: schema_versionは固定文字列とする（設計書データ構造編9章 未決事項D-04、2026-08-25解消）。
#: 単一利用者・ローカル運用のv1では複数版の共存・自動移行を扱わない。スキーマ変更時に
#: この値を上げ、その時点でインポート側の移行方針を再検討する。
#: 1.1: リソース配分のスロット単位化に伴い、実績推移へ時間枠別内訳（slot_minutes）を追加。
SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class ExportSelection:
    """出力項目選択（仕様書6.10）。既定値は同節の表に合わせ、日記本文・AI対話履歴のみ
    既定で除外する。"""

    goal_overview: bool = True
    materials: bool = True
    summary: bool = True
    daily_records: bool = True
    quality_trend: bool = True
    replan_history: bool = True
    weekly_summaries: bool = True
    recap_themes: bool = True
    diary: bool = False
    ai_dialogue: bool = False
    exam_results: bool = True
    retrospective: bool = True


@dataclass(frozen=True)
class ExportContent:
    data: dict
    markdown: str
    markdown_path: Path | None = None
    json_path: Path | None = None


def build_export_data(
    session: Session,
    goal: Goal,
    selection: ExportSelection,
    *,
    today: dt.date,
    treat_holiday_as_buffer: bool,
    anonymized: bool,
) -> dict:
    """データ構造編7.1のJSONスキーマに沿ってエクスポートデータを組み立てる。

    anonymized=True の場合、weekly_summaries・retrospective は匿名化版レコードのみを参照する
    （元版へフォールバックしない。フォールバックすると匿名化の目的が果たせないため、
    未生成であれば空のまま返す。呼び出し元 execute_export が事前に匿名化版を生成する）。

    カテゴリ別の実際の組み立ては`export_service_exam`/`export_service_reading`/
    `export_service_work`へ委譲する。本関数側でこれら3モジュールを先頭でimportすると、
    各モジュールが本モジュールの`ExportSelection`等を先頭でimportしているため循環import
    になる。呼び出し時（本関数が実際に呼ばれる時点では3モジュールとも読み込み済み）まで
    遅延させてimportすることで回避する（実装フェーズ分割計画書S02、record_serviceの
    register_progressと同じ方針）。
    """
    from app.services import export_service_exam, export_service_reading, export_service_work

    data: dict = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "anonymized": anonymized,
    }

    if goal.category == GoalCategory.READING:
        return export_service_reading.build_reading_export_data(
            session, goal, selection, anonymized=anonymized, data=data
        )
    if goal.category == GoalCategory.WORK:
        return export_service_work.build_work_export_data(
            session, goal, selection, anonymized=anonymized, data=data
        )

    return export_service_exam.build_exam_export_data(
        session,
        goal,
        selection,
        today=today,
        treat_holiday_as_buffer=treat_holiday_as_buffer,
        anonymized=anonymized,
        data=data,
    )


def render_markdown(
    data: dict, selection: ExportSelection, category: GoalCategory = GoalCategory.EXAM
) -> str:
    """データ構造編7.2のMarkdown構成に沿って本文を生成する（カテゴリ別の委譲はbuild_export_data
    と同じ理由で遅延import、実装フェーズ分割計画書S02）。"""
    from app.services import export_service_exam, export_service_reading, export_service_work

    if category == GoalCategory.READING:
        return export_service_reading.render_reading_markdown(data)
    if category == GoalCategory.WORK:
        return export_service_work.render_work_markdown(data)
    return export_service_exam.render_exam_markdown(data)


def _safe_filename_fragment(name: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("_", name).strip() or "goal"


def write_export_files(goal: Goal, content: ExportContent) -> tuple[Path, Path]:
    """Markdown・JSONの両形式をファイルへ出力する（仕様書6.10「ファイルの出力」、
    データ構造編8章ディレクトリ構成「data/ ...エクスポート」）。
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    base_name = f"{_safe_filename_fragment(goal.name)}_{timestamp}"
    markdown_path = EXPORT_DIR / f"{base_name}.md"
    json_path = EXPORT_DIR / f"{base_name}.json"

    markdown_path.write_text(content.markdown, encoding="utf-8")
    json_path.write_text(json.dumps(content.data, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def execute_export(
    session: Session,
    goal: Goal,
    selection: ExportSelection,
    *,
    anonymize: bool,
) -> ExportContent:
    """ナレッジエクスポートを実行する（仕様書6.10「操作: 総括レポートの生成および再生成、
    出力項目の選択、プレビュー表示、ファイルの出力」のうち実行部分）。

    anonymize=True の場合、事前に週次要約・総括レポートの匿名化版を生成してから
    組み立てる（データ構造編7.3）。既存の匿名化版がある場合は最新内容へ更新する。
    プレビュー（GET .../preview）はbuild_export_dataのみを呼び、本関数（ファイル書き出しと
    匿名化再生成を伴う実行）とは区別する。

    複数回のAI呼び出し（週次要約1件ずつ＋総括レポート）を伴うため、進捗を
    app.services.export_progress へ記録する（実装フェーズ分割計画書Phase10注意点）。
    フロントエンドはGET /goals/{goal_id}/knowledge-export/progress をポーリングして表示する。
    """
    from app.services import export_service_work

    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)

    if anonymize:
        if goal.category == GoalCategory.WORK:
            # 仕事目標は総括レポート（EXAM/READING専用）を持たないため、既存の
            # goal_retrospective（period_type問わず、非匿名化版）それぞれについて
            # 匿名化版を再生成する（データ構造編7.1「仕事目標の場合」、要件定義書R-81）。
            existing = export_service_work.build_work_retrospectives(
                session, goal, anonymized=False
            )
            export_progress.start(goal.id, total=len(existing) or 1)
            try:
                for row in existing:
                    if row["period_type"] == RetrospectivePeriodType.MONTHLY.value:
                        work_report_service.generate_monthly_report(
                            session, goal, period_key=row["period_key"], today=today, anonymize=True
                        )
                    else:
                        work_report_service.generate_semiannual_review(
                            session, goal, period_key=row["period_key"], today=today, anonymize=True
                        )
                    export_progress.advance(goal.id)
            finally:
                export_progress.finish(goal.id)
        else:
            # 総括・読了レポートは完了した目標のみ持つ（retrospective_service）。
            # 完了していない目標では匿名化版のAI再生成を行わず、週次要約の匿名化だけを行う
            # （利用者方針2026-10-04）。
            has_completed_report = retrospective_service.can_generate_retrospective(goal)
            total = weekly_summary_service.count_pending_anonymization_weeks(session, goal) + (
                1 if has_completed_report else 0
            )
            export_progress.start(goal.id, total=total)
            try:
                weekly_summary_service.regenerate_all_weekly_summaries_anonymized(
                    session, goal, on_progress=lambda: export_progress.advance(goal.id)
                )
                if has_completed_report:
                    retrospective_service.generate_retrospective(
                        session, goal, today=today, anonymize=True
                    )
                    export_progress.advance(goal.id)
            finally:
                export_progress.finish(goal.id)

    data = build_export_data(
        session,
        goal,
        selection,
        today=today,
        treat_holiday_as_buffer=treat_holiday_as_buffer,
        anonymized=anonymize,
    )
    markdown = render_markdown(data, selection, goal.category)
    content = ExportContent(data=data, markdown=markdown)
    markdown_path, json_path = write_export_files(goal, content)
    return ExportContent(
        data=data, markdown=markdown, markdown_path=markdown_path, json_path=json_path
    )
