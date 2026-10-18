"""AIプロンプトへ注入する変数の組み立て（設計書 ロジック・プロンプト編17.2〜17.4）。

どの値をプロンプトへ渡すかは業務判断であり、ai/パッケージの責務外（データ構造編8.1
「ai: 禁止事項=業務判断」）のためservices層に置く。既存のPhase2〜4サービス
（goal_service・cycle_service・quota_service・speed_service・slot_service・
metrics_service・material_service）を組み合わせるのみで、算出ロジック自体は再実装しない
（CLAUDE.md DRYの原則）。

本モジュールは、目標の種類（資格試験・読書・仕事）を問わず2カテゴリ以上から参照される
共通処理を置く（実装フェーズ分割計画書S01、`ai_context_service.py`からの分割）。
カテゴリ固有の処理は`ai_context_exam.py`・`ai_context_reading.py`・`ai_context_work.py`に
分割して置く。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.prompt_builder import DatedLogEntry
from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.record import WeeklySummary


def list_active_goals(session: Session) -> list[Goal]:
    """進行中（ACTIVE）の目標一覧を取得する（種別を問わない。dashboard.py等の汎用的な
    「進行中の目標一覧」表示で使用）。"""
    return session.query(Goal).filter(Goal.status == GoalStatus.ACTIVE).order_by(Goal.id).all()


def list_daily_message_target_goals(session: Session) -> list[Goal]:
    """今日の一言（DAILY_MESSAGE）の対象となる進行中（ACTIVE）の目標一覧を取得する。

    対象はEXAM・WORK（要件定義書R-77）。READINGは要件定義書6.10により対象外のまま
    （読書用の一言相当機能は設けない設計）。list_active_exam_goalsとは別の関数とする
    のは、既存のDAILY_FEEDBACK・DAILY_MESSAGEがEXAM専用として`list_active_exam_goals`に
    依存し続けられるようにするため（実装フェーズ分割計画書Phase22）。
    """
    return (
        session.query(Goal)
        .filter(
            Goal.status == GoalStatus.ACTIVE,
            Goal.category.in_([GoalCategory.EXAM, GoalCategory.WORK]),
        )
        .order_by(Goal.id)
        .all()
    )


def _format_days_remaining(today: dt.date, target: dt.date) -> str:
    days = (target - today).days
    if days >= 0:
        return f"残り{days}日"
    return f"{-days}日超過"


def _format_weekly_summary_entry(row: WeeklySummary) -> DatedLogEntry:
    return DatedLogEntry(
        record_date=row.week_start_date,
        text=f"[{row.week_start_date.isoformat()}〜{row.week_end_date.isoformat()}]\n"
        f"{row.summary_body}",
    )


@dataclass(frozen=True)
class WeeklyCompressedPeriod:
    """対象期間[period_start, period_end]（両端含む）のうち、週次要約バッチ
    （weekly_summary_service.run_retroactive_generation）が既に生成済みの週を圧縮表現へ、
    まだ生成されていない部分は生ログのまま呼び出し側が注入する境界の解決結果
    （日次報告フィードバック17.6・17.8、総括レポート系17.5・17.7・17.9・17.10で共通、L-11）。

    period_start（goal.start_date・book.start_date・対象月/半期の初日等）は
    週次要約の週区切り（月曜始まり、15.1）と一致するとは限らないため、「period_startから
    連続する週のみ圧縮対象」という判定は行わない（一致しないケースでは圧縮が実質
    発動しなくなるバグになるため、2026-09-16是正）。[period_start, period_end]に
    フル収まる週次要約はすべて圧縮対象とし、間に未生成の週（欠け）があっても構わない
    （生ログ側がexclude_covered_datesでその欠けた週の日付を除外しないため、欠けた週は
    自然に生ログのまま残る＝情報が失われない）。
    """

    weekly_summary_entries: list[DatedLogEntry]  # 古い順
    covered_ranges: list[tuple[dt.date, dt.date]]  # 圧縮対象の各週の(開始日, 終了日)。古い順


def resolve_weekly_compressed_period(
    session: Session,
    goal: Goal,
    period_start: dt.date,
    period_end: dt.date,
    *,
    limit: int | None = None,
) -> WeeklyCompressedPeriod:
    """[period_start, period_end]内に完全に収まる週次要約を古い順に列挙する。
    呼び出し側は、生ログのビルダーが返した list[DatedLogEntry] へ
    exclude_covered_dates(entries, result.covered_ranges) を適用し、圧縮済みの日付を
    生ログ側から除外する（二重注入を避ける。日付単位の除外のため、period_start・
    period_endの週境界との不一致や週の欠けがあっても正しく動く）。

    週次要約が1件も無い場合はcovered_ranges=[]となり、生ログ側は無加工のまま
    （＝全期間が生ログとして注入される、要約バッチが未実行でも情報が失われない
    安全側の設計）。

    limitを指定すると、period_end側に近い（新しい）方からlimit件までに絞る
    （古い方から溢れた分は圧縮対象から除外＝生ログ側にも現れず、weekly_summariesにも
    現れない）。日次報告フィードバック（`build_past_record_entries`経由）・読了レポート・
    月次報告・半期評価はいずれもlimit=None（対象期間全体を漏れなく圧縮対象とする、
    S04で日次報告フィードバックもこの方式へ統一。旧実装はsummary.inject_weeksで
    直近側の件数を絞っていたが、2026-10-17のS04で上限自体を撤廃した）。
    """
    query = session.query(WeeklySummary).filter(
        WeeklySummary.goal_id == goal.id,
        WeeklySummary.is_anonymized.is_(False),
        WeeklySummary.week_start_date >= period_start,
        WeeklySummary.week_end_date <= period_end,
    )
    if limit is None:
        rows = query.order_by(WeeklySummary.week_start_date).all()
    else:
        rows = list(
            reversed(query.order_by(WeeklySummary.week_start_date.desc()).limit(limit).all())
        )
    return WeeklyCompressedPeriod(
        weekly_summary_entries=[_format_weekly_summary_entry(row) for row in rows],
        covered_ranges=[(row.week_start_date, row.week_end_date) for row in rows],
    )


def exclude_covered_dates(
    entries: list[DatedLogEntry], covered_ranges: list[tuple[dt.date, dt.date]]
) -> list[DatedLogEntry]:
    """生ログのエントリ列から、covered_ranges（resolve_weekly_compressed_periodが返した、
    週次要約で圧縮済みの週の日付範囲）に含まれる日付のものを取り除く（L-11）。
    """
    if not covered_ranges:
        return entries
    return [
        entry
        for entry in entries
        if not any(start <= entry.record_date <= end for start, end in covered_ranges)
    ]


@dataclass(frozen=True)
class PastRecordEntries:
    """日次報告フィードバックが送る「過去の記録」（目標開始日〜対象日の前日、全期間、
    件数・週数の上限なし）の組み立て結果（S04、G1・G2共通化）。

    weekly_summary_entries・raw_entriesのいずれも古い順。raw_entriesは、
    weekly_summary_entriesで圧縮済みの日付をexclude_covered_datesで除外済みのため、
    テンプレートへそのまま渡してよい（二重注入なし）。
    """

    weekly_summary_entries: list[DatedLogEntry]
    raw_entries: list[DatedLogEntry]


def build_past_record_entries(
    session: Session,
    goal: Goal,
    period_start: dt.date,
    period_end: dt.date,
    raw_entries: list[DatedLogEntry],
) -> PastRecordEntries:
    """[period_start, period_end]全期間を対象に、週次要約済みの週は圧縮表現へ、
    まだ要約されていない日は生ログ（raw_entries）のまま渡すための組み立て処理
    （S04、資格試験・読書・仕事の3カテゴリで共通、CLAUDE.md DRYの原則）。

    件数・週数の上限は設けない（limit=None）。raw_entriesは呼び出し側が
    period_start〜period_endの範囲でカテゴリ固有のクエリにより組み立てたものを渡す
    （整形方法はカテゴリごとに異なるため、本関数の責務外）。
    """
    compressed = resolve_weekly_compressed_period(
        session, goal, period_start, period_end, limit=None
    )
    return PastRecordEntries(
        weekly_summary_entries=compressed.weekly_summary_entries,
        raw_entries=exclude_covered_dates(raw_entries, compressed.covered_ranges),
    )


def build_anonymize_instruction(anonymize: bool) -> str:
    """{{anonymize}}: 匿名化の指示（匿名化版生成時のみ、17.5、データ構造編7.3）。"""
    if not anonymize:
        return ""
    return (
        "# 匿名化の指示\n"
        "業務・家庭など個人や勤務先を特定しうる固有の事情への言及を避け、"
        "一般化して記述してください。"
    )


#: {{perspective_suggestion}}のカテゴリ別文面（S-4 4-3）。まだ実績が少ない段階でAIが
#: 傾向を断定してしまわないよう、複数の観点から問いかけるよう促す（前回セッション提示の
#: 初日体験改善案B「初日のAI応答強化」に相当）。
_PERSPECTIVE_SUGGESTION_TEXTS: dict[GoalCategory, str] = {
    GoalCategory.EXAM: (
        "# 記録がまだ少ない場合\n"
        "まだ記録が数回に満たない学習者です。学習の傾向や課題を断定せず、"
        "生活リズムや学習のしやすさ、気になっていることなど複数の観点から問いかけ、"
        "学習者自身の言語化を促してください。"
    ),
    GoalCategory.READING: (
        "# 記録がまだ少ない場合\n"
        "まだ記録が数回に満たない読者です。読み方の傾向を断定せず、"
        "読みやすさや興味を持った点、読む時間帯など複数の観点から問いかけ、"
        "本人の言語化を促してください。"
    ),
    GoalCategory.WORK: (
        "# 記録がまだ少ない場合\n"
        "まだ記録が数回に満たない働き手です。業務の傾向を断定せず、"
        "業務のしやすさや工夫した点、気になっていることなど複数の観点から問いかけ、"
        "本人の言語化を促してください。"
    ),
}


def build_perspective_suggestion_instruction(
    category: GoalCategory, is_below_threshold: bool
) -> str:
    """{{perspective_suggestion}}: 記録件数が閾値未満の学習者への追加指示（S-4 4-3）。

    判定（件数の集計・閾値との比較）は呼び出し側（各*_feedback_service）が行い、
    ここは真偽値から文面を組み立てるだけに徹する（build_anonymize_instructionと同じ
    分担、業務判断はservices層・文字列組み立てはこちらという役割分担）。
    """
    if not is_below_threshold:
        return ""
    return _PERSPECTIVE_SUGGESTION_TEXTS[category]
