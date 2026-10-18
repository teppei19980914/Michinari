"""プロンプト組み立てと段階的縮退（設計書 ロジック・プロンプト編16.5、17章）。

プロンプト文面は prompt_template テーブルから読む（呼び出し側の責務）。本モジュールは
テンプレート本文と変数を受け取り、`{{変数名}}` を置換したうえで、文字数が閾値を超える
場合に段階的に縮退する、純粋な文字列組み立てのみを担う（業務判断=どの値を変数に
渡すかはservices層の責務、データ構造編8.1）。

資格試験の日次報告フィードバック（DAILY_FEEDBACK）は、週次要約が無い過去日の生ログ
（{{recent_logs}}）と教材の集約表示という固有の段階を持つため専用の`build_daily_feedback`
（16.5、S04で3段階へ改訂）を使う。それ以外の用途（読書・仕事の日次報告フィードバック、総括
レポート・読了レポート・月次報告・半期評価）は「固定変数＋古い順エントリ列（複数可）＋任意の
当日対話」という共通の形に収まるため、汎用の`build_with_degradable_entries`で縮退する
（DegradableFeedbackContext参照）。過去になるほど情報の鮮度が落ちるという考え方はいずれも
共通のため、「古い記録から削る」方針を踏襲する。日次報告フィードバック3用途（資格試験・読書・
仕事）はいずれも、当日の入力（本日の実績・日記・対話）を縮退の対象にしない（S04決定事項D1）。
過去の記録を使い切ってもなお上限を超える場合は、切り詰めずに送信を中止する
（`BuildResult.exhausted`／`exceeds_with_entries_emptied`参照）。
"""

import datetime as dt
import re
from dataclasses import dataclass, field

from app.constants.enums import ChatRole

#: テンプレートのプレースホルダー（`{{変数名}}`）。
_PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")


def _substitute(template: str, variables: dict[str, str]) -> str:
    """テンプレートの `{{変数名}}` を1回のパス処理で展開する。

    値の中に現れた `{{...}}` は再展開しない。変数を1つずつ `replace` すると、利用者の入力
    （日記・目標名・ヘルプ質問など）に含まれる `{{...}}` が後続の変数として展開され、
    プロンプトの構造を書き換えられてしまうため（テンプレート注入）。定義のない変数名は
    そのまま残す（従来の挙動と同じ）。
    """
    return _PLACEHOLDER_PATTERN.sub(
        lambda match: variables.get(match.group(1), match.group(0)), template
    )


@dataclass(frozen=True)
class BuildResult:
    """組み立て結果（ai_logへの記録に用いる、16.8）。

    exhausted: 日次報告フィードバック（S04）専用のフラグ。当日の入力（実績・日記・
    対話）を一切縮退せずに保持したまま、縮退可能な過去の記録（週次要約・生ログ・
    資格試験の教材集約表示）を全て使い切ってもmax_charsを超える場合にTrueとなる。
    この場合、textは切り詰めていない（NewtonX利用ナレッジ「切り詰めない」）。
    呼び出し側（daily_feedback_service等）はexhausted=Trueの場合、AIへ送信せず
    DailyFeedbackPromptTooLongErrorを送出する。build_simple・build_with_degradable_entries
    （日次報告以外の用途）は常にFalseを返す（既存の末尾切り詰めフォールバックを維持する、
    S04決定事項D2）。
    """

    text: str
    prompt_chars: int
    was_truncated: bool
    exhausted: bool = False


@dataclass(frozen=True)
class MaterialStatusEntry:
    """教材ごとの計画状態1件分（17.2 {{material_status}}）。"""

    due_date: dt.date
    text: str


@dataclass(frozen=True)
class ChatTurn:
    """本日の対話1往復分の一方（17.2 {{conversation_history}}）。"""

    role: ChatRole
    content: str


@dataclass(frozen=True)
class DatedLogEntry:
    """日付付きの記録・週次要約1件分（複数の用途で共通、17.6・17.8・17.7・17.9・17.10・
    17.5）。呼び出し側は record_date（週次要約の場合は週の開始日）の古い順（昇順）で渡す。
    text は見出し（【日付 見出し】や[週範囲]等、用途ごとに書式が異なる）を含めて整形済みの
    文字列とする（整形方法はai_context_common／ai_context_exam／ai_context_reading／
    ai_context_work側の責務。MaterialStatusEntryと同じ、
    「日付＋整形済みテキスト」の形に揃える、CLAUDE.md DRYの原則）。
    build_with_degradable_entriesの各段階で、リスト先頭＝最も古い記録から除外する
    （過去になるほど情報の鮮度が落ちるため）。
    """

    record_date: dt.date
    text: str


@dataclass
class DailyFeedbackContext:
    """日次報告フィードバック（DAILY_FEEDBACK）の注入変数（17.2）。"""

    today: str
    day_type: str
    load_coefficient: str
    goal_summary: str
    material_entries: list[MaterialStatusEntry]
    slot_summary: str
    buffer_usage_rate: str
    today_logs: str
    diary_body: str
    diary_learned: str
    weekly_summary_entries: list[DatedLogEntry] = field(default_factory=list)  # 古い順
    recent_log_entries: list[DatedLogEntry] = field(default_factory=list)  # 古い順（S04 G2）
    conversation_history: list[ChatTurn] = field(default_factory=list)  # 古い順（縮退対象外、S04）
    #: {{perspective_suggestion}}: 記録件数が閾値未満の場合の追加指示（S-4 4-3）。
    #: 空文字なら何も注入しない（build_anonymize_instructionと同じ方式）。
    perspective_suggestion: str = ""


_NO_MATERIALS_TEXT = "（対象教材はありません）"
_NO_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"
_NO_RECENT_LOGS_TEXT = "（週次要約が無い過去日の記録はありません）"
_NO_CONVERSATION_TEXT = "（本日はまだ対話していません）"
_CHAT_ROLE_LABELS = {ChatRole.USER: "学習者", ChatRole.ASSISTANT: "AI"}


def _format_materials(entries: list[MaterialStatusEntry], collapsed_count: int) -> str:
    lines = [entry.text for entry in entries]
    if collapsed_count:
        lines.append(f"（締切が遠い教材 {collapsed_count} 件は集約表示のため省略）")
    return "\n".join(lines) if lines else _NO_MATERIALS_TEXT


def format_conversation_history(turns: list[ChatTurn]) -> str:
    """{{conversation_history}}の共通フォーマット。当日対話を持つ全用途（DAILY_FEEDBACK・
    DAILY_FEEDBACK_READING・DAILY_FEEDBACK_WORK）で使う（build_daily_feedback・
    build_with_degradable_entries、CLAUDE.md DRYの原則）。
    """
    if not turns:
        return _NO_CONVERSATION_TEXT
    return "\n".join(f"【{_CHAT_ROLE_LABELS[turn.role]}】{turn.content}" for turn in turns)


def _join_dated_entries(entries: list[DatedLogEntry], empty_text: str) -> str:
    if not entries:
        return empty_text
    return "\n\n".join(entry.text for entry in entries)


def build_daily_feedback(
    template_body: str, context: DailyFeedbackContext, max_chars: int
) -> BuildResult:
    """DAILY_FEEDBACKのプロンプトを組み立て、必要なら縮退する（S04、16.5改訂）。

    当日の入力（本日の実績・日記・対話）は縮退の対象にしない（S04決定事項D1）。
    縮退順は、①週次要約を古い順に0件まで→②週次要約が無い過去日の生ログ
    （recent_log_entries）を古い順に0件まで→③締切が遠い教材を集約表示、の3段階
    （D7・D8）。これでも上限を超える場合は、当日の入力を切り詰めず送信しない
    （exhausted=True、NewtonX利用ナレッジ「切り詰めない」）。
    """
    materials = list(context.material_entries)
    weekly_summaries = list(context.weekly_summary_entries)
    recent_logs = list(context.recent_log_entries)
    collapsed_count = 0

    def render() -> str:
        variables = {
            "today": context.today,
            "day_type": context.day_type,
            "load_coefficient": context.load_coefficient,
            "goal_summary": context.goal_summary,
            "material_status": _format_materials(materials, collapsed_count),
            "slot_summary": context.slot_summary,
            "buffer_usage_rate": context.buffer_usage_rate,
            "today_logs": context.today_logs,
            "diary_body": context.diary_body,
            "diary_learned": context.diary_learned,
            "weekly_summaries": _join_dated_entries(weekly_summaries, _NO_WEEKLY_SUMMARIES_TEXT),
            "recent_logs": _join_dated_entries(recent_logs, _NO_RECENT_LOGS_TEXT),
            "conversation_history": format_conversation_history(context.conversation_history),
            "perspective_suggestion": context.perspective_suggestion,
        }
        return _substitute(template_body, variables)

    text = render()
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)

    was_truncated = False

    # 段階1：週次要約を古い順（リスト先頭）に1件ずつ除外する（D7：下限なし）。
    while weekly_summaries and len(text) > max_chars:
        weekly_summaries.pop(0)
        was_truncated = True
        text = render()

    # 段階2：週次要約が無い過去日の生ログを古い順に1件ずつ除外する（D8、S04 G2）。
    while recent_logs and len(text) > max_chars:
        recent_logs.pop(0)
        was_truncated = True
        text = render()

    # 段階3：締切が遠い教材の情報を集約表示に置き換える（16.5）。
    if len(text) > max_chars and materials:
        materials.sort(key=lambda entry: entry.due_date)  # 締切が近い順（末尾ほど遠い）
        while len(materials) > 1 and len(text) > max_chars:
            materials.pop()
            collapsed_count += 1
            was_truncated = True
            text = render()

    if len(text) > max_chars:
        return BuildResult(
            text=text, prompt_chars=len(text), was_truncated=True, exhausted=True
        )

    return BuildResult(text=text, prompt_chars=len(text), was_truncated=was_truncated)


@dataclass
class DegradableEntryStage:
    """段階的縮退の1段階分（DatedLogEntryのリスト1つに対応する変数1つ）。

    entriesは古い順（昇順）。超過時はリスト先頭＝最も古い記録から1件ずつ除外する。
    複数段階を持つ用途（例：日次報告フィードバックの週次要約→直近記録の2段階）は、
    DegradableFeedbackContext.stagesに古い情報を持つ段階から順に並べる。先の段階が尽きる
    （0件になる）までは後の段階に着手しない（16.5の「ある段階が尽きるまで次の段階へ進まない」
    という既存方針を、段階数が可変でも保てるようにするため）。
    """

    key: str  # テンプレート変数名
    entries: list[DatedLogEntry]
    empty_text: str


@dataclass
class DegradableFeedbackContext:
    """1つ以上の「古い順エントリ列」＋任意の当日対話を持つプロンプトの共通の注入変数構成。

    資格試験（16.5、build_daily_feedback）以外の全用途（読書・仕事の日次報告フィードバック
    17.6・17.8、総括レポート・読了レポート・月次報告・半期評価 17.5・17.7・17.9・17.10）が、
    「固定変数＋古い順エントリ列（複数可）＋任意の当日対話」という共通の形に収まるため、
    ここへ集約する（CLAUDE.md DRYの原則）。資格試験のDAILY_FEEDBACKは、教材の集約表示という
    固有の段階を持つため、本エンジンとは別のbuild_daily_feedbackのままとする（無用な複雑化を
    避けるため統合しない。当日の入力を縮退しない・使い切ったら送信を中止するという原則自体は
    S04で3用途共通にしてある、D1・D2）。
    """

    fixed_variables: dict[str, str]  # 縮退対象外の変数（today・goal_summary等）
    stages: list[DegradableEntryStage] = field(default_factory=list)  # 古い情報を持つ段階から順に
    conversation_history: list[ChatTurn] = field(default_factory=list)  # 古い順。最後の段階で除外


def build_with_degradable_entries(
    template_body: str, context: DegradableFeedbackContext, max_chars: int
) -> BuildResult:
    """固定変数＋古い順エントリ列（複数可）＋任意の当日対話からプロンプトを組み立て、
    必要なら段階的に縮退する。過去になるほど情報の鮮度が落ちるという考え方で
    「古いものから削る」方針を踏襲する（16.5と同じ考え方、DatedLogEntryのdocstring参照）。

    stagesに与えた順に、各段階のエントリを古い日から使い切るまで削り、次いで当日対話を
    古い往復から削り、それでも超える場合は末尾を切り詰める（build_simpleと同じフェイルセーフ。
    固定変数自体が極端に大きい場合のみ到達する想定）。
    """
    stages = [
        DegradableEntryStage(key=s.key, entries=list(s.entries), empty_text=s.empty_text)
        for s in context.stages
    ]
    history = list(context.conversation_history)

    def render() -> str:
        variables = dict(context.fixed_variables)
        for stage in stages:
            variables[stage.key] = _join_dated_entries(stage.entries, stage.empty_text)
        variables["conversation_history"] = format_conversation_history(history)
        return _substitute(template_body, variables)

    text = render()
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)

    was_truncated = False

    for stage in stages:
        while stage.entries and len(text) > max_chars:
            stage.entries.pop(0)
            was_truncated = True
            text = render()

    while history and len(text) > max_chars:
        history.pop(0)
        was_truncated = True
        text = render()

    if len(text) > max_chars:
        was_truncated = True
        text = text[:max_chars]

    return BuildResult(text=text, prompt_chars=len(text), was_truncated=was_truncated)


def exceeds_with_entries_emptied(
    template_body: str, context: DegradableFeedbackContext, max_chars: int
) -> bool:
    """全stageのentriesを0件にした場合（当日対話・固定変数はそのまま）でも
    max_charsを超えるかを判定する（S04、読書・仕事の日次報告フィードバック専用）。

    当日の入力（当日対話を含む）は縮退の対象にしない（S04決定事項D1）ため、
    build_with_degradable_entries自体は変更せず（D2、他5用途への影響を避ける）、
    呼び出し側がこの事前判定でTrueの場合はbuild_with_degradable_entriesを呼ばずに
    送信を中止する。Falseの場合、過去記録を全て削れば必ず収まることが保証されるため、
    build_with_degradable_entriesの対話履歴トリミング・末尾切り詰めフォールバックには
    到達しない（stageのエントリ除外だけで必ず収まる）。
    """
    variables = dict(context.fixed_variables)
    for stage in context.stages:
        variables[stage.key] = stage.empty_text
    variables["conversation_history"] = format_conversation_history(context.conversation_history)
    return len(_substitute(template_body, variables)) > max_chars


def build_simple(template_body: str, variables: dict[str, str], max_chars: int) -> BuildResult:
    """DAILY_MESSAGEなど、縮退段階が定義されていない用途向けの単純組み立て。

    上限を超える場合は末尾を切り詰める（情報量が少なく実運用では到達しない想定のフェイルセーフ。
    段階的縮退が必要な用途はbuild_daily_feedback（資格試験のDAILY_FEEDBACK専用）または
    build_with_degradable_entries（それ以外）を使う。本関数を使い続けるのは、
    どちらの対象にもならない用途のみ）。
    """
    text = _substitute(template_body, variables)
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)
    return BuildResult(text=text[:max_chars], prompt_chars=max_chars, was_truncated=True)
