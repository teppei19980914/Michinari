"""プロンプト組み立てと段階的縮退（設計書 ロジック・プロンプト編16.5、17章）。

プロンプト文面は prompt_template テーブルから読む（呼び出し側の責務）。本モジュールは
テンプレート本文と変数を受け取り、`{{変数名}}` を置換したうえで、文字数が閾値を超える
場合に段階的に縮退する、純粋な文字列組み立てのみを担う（業務判断=どの値を変数に
渡すかはservices層の責務、データ構造編8.1）。

資格試験（DAILY_FEEDBACK）は週次要約・教材という圧縮済みの情報源を持つため16.5の4段階、
読書・仕事（DAILY_FEEDBACK_READING・DAILY_FEEDBACK_WORK）は週次要約を持たず直近の原文
記録を直接注入する設計（21.4・22.4）のため、共通の3段階（`build_recent_log_feedback`）
で縮退する。過去になるほど情報の鮮度が落ちるという考え方は共通のため、いずれも
「古い記録から削る」方針を踏襲する。
"""

import datetime as dt
from dataclasses import dataclass, field

from app.constants.domain import PROMPT_DIARY_TRIM_CHUNK_CHARS
from app.constants.enums import ChatRole


def _substitute(template: str, variables: dict[str, str]) -> str:
    text = template
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    return text


@dataclass(frozen=True)
class BuildResult:
    """組み立て結果（ai_logへの記録に用いる、16.8）。"""

    text: str
    prompt_chars: int
    was_truncated: bool


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
    """日付付きの記録1件分（読書の{{recent_recalls}}・仕事の{{recent_work_logs}}で共通、
    17.6・17.8）。呼び出し側は record_date の古い順（昇順）で渡す。build_recent_log_feedback
    の段階1で、リスト先頭＝最も古い記録から除外する（過去になるほど情報の鮮度が落ちるため）。
    """

    record_date: dt.date
    label: str
    body: str


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
    weekly_summaries: list[str] = field(default_factory=list)  # 新しい順
    conversation_history: list[ChatTurn] = field(default_factory=list)  # 古い順


_NO_MATERIALS_TEXT = "（対象教材はありません）"
_NO_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"
_NO_CONVERSATION_TEXT = "（本日はまだ対話していません）"
_CHAT_ROLE_LABELS = {ChatRole.USER: "学習者", ChatRole.ASSISTANT: "AI"}


def _format_materials(entries: list[MaterialStatusEntry], collapsed_count: int) -> str:
    lines = [entry.text for entry in entries]
    if collapsed_count:
        lines.append(f"（締切が遠い教材 {collapsed_count} 件は集約表示のため省略）")
    return "\n".join(lines) if lines else _NO_MATERIALS_TEXT


def _format_weekly_summaries(summaries: list[str]) -> str:
    return "\n\n".join(summaries) if summaries else _NO_WEEKLY_SUMMARIES_TEXT


def format_conversation_history(turns: list[ChatTurn]) -> str:
    """{{conversation_history}}の共通フォーマット。DAILY_FEEDBACK・DAILY_FEEDBACK_READING・
    DAILY_FEEDBACK_WORKの3用途で使う（build_daily_feedback・build_recent_log_feedback、
    CLAUDE.md DRYの原則）。
    """
    if not turns:
        return _NO_CONVERSATION_TEXT
    return "\n".join(f"【{_CHAT_ROLE_LABELS[turn.role]}】{turn.content}" for turn in turns)


def _format_dated_log_entries(entries: list[DatedLogEntry], empty_text: str) -> str:
    if not entries:
        return empty_text
    return "\n\n".join(
        f"【{entry.record_date.isoformat()} {entry.label}】\n{entry.body}" for entry in entries
    )


def build_daily_feedback(
    template_body: str, context: DailyFeedbackContext, max_chars: int
) -> BuildResult:
    """DAILY_FEEDBACKのプロンプトを組み立て、必要なら16.5の4段階で縮退する。"""
    materials = list(context.material_entries)
    weekly_summaries = list(context.weekly_summaries)
    history = list(context.conversation_history)
    diary_body = context.diary_body
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
            "diary_body": diary_body,
            "diary_learned": context.diary_learned,
            "weekly_summaries": _format_weekly_summaries(weekly_summaries),
            "conversation_history": format_conversation_history(history),
        }
        return _substitute(template_body, variables)

    text = render()
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)

    was_truncated = False

    # 段階1：週次要約を古い順（リスト末尾）に1件ずつ除外する（最低1件は残す、16.5）。
    while len(weekly_summaries) > 1 and len(text) > max_chars:
        weekly_summaries.pop()
        was_truncated = True
        text = render()

    # 段階2：締切が遠い教材の情報を集約表示に置き換える（16.5）。
    if len(text) > max_chars and materials:
        materials.sort(key=lambda entry: entry.due_date)  # 締切が近い順（末尾ほど遠い）
        while len(materials) > 1 and len(text) > max_chars:
            materials.pop()
            collapsed_count += 1
            was_truncated = True
            text = render()

    # 段階3：当日の対話履歴を古い往復（リスト先頭）から除外する（16.5）。
    while history and len(text) > max_chars:
        history.pop(0)
        was_truncated = True
        text = render()

    # 段階4：日記本文を先頭から切り詰める（末尾＝直近の状況を優先して残す、16.5）。
    while diary_body and len(text) > max_chars:
        diary_body = diary_body[PROMPT_DIARY_TRIM_CHUNK_CHARS:]
        was_truncated = True
        text = render()

    return BuildResult(text=text, prompt_chars=len(text), was_truncated=was_truncated)


@dataclass
class RecentLogFeedbackContext:
    """読書（DAILY_FEEDBACK_READING）・仕事（DAILY_FEEDBACK_WORK）の日次報告フィードバックで
    共通の注入変数構成（17.6・17.8）。資格試験と異なり週次要約・教材のような圧縮済みの
    情報源を持たないため、変数を「縮退対象外の固定変数」と「直近記録（段階1）」
    「当日対話（段階2）」の3種に絞って共通化する（CLAUDE.md DRYの原則）。
    """

    fixed_variables: dict[str, str]  # today・book_summary/work_summary・today_recall/today_work等
    recent_logs: list[DatedLogEntry]  # 古い順。段階1で古い日から除外
    recent_logs_key: str  # テンプレート変数名（"recent_recalls" または "recent_work_logs"）
    recent_logs_empty_text: str
    conversation_history: list[ChatTurn] = field(default_factory=list)  # 古い順。段階2で除外


def build_recent_log_feedback(
    template_body: str, context: RecentLogFeedbackContext, max_chars: int
) -> BuildResult:
    """DAILY_FEEDBACK_READING・DAILY_FEEDBACK_WORKのプロンプトを組み立て、必要なら段階的に
    縮退する。読書・仕事は資格試験（16.5）と異なり週次要約・教材を持たないため、直近記録と
    当日対話の2つを対象に、過去になるほど情報の鮮度が落ちるという考え方で「古いものから削る」
    2段階＋末尾切り詰めのフェイルセーフとする。

    段階1：直近記録（{{recent_recalls}}・{{recent_work_logs}}）を古い日（リスト先頭）から
           除外する（16.5の段階3「古い往復から除外」と同じ考え方を日単位に適用）。
    段階2：当日の対話履歴を古い往復（リスト先頭）から除外する（16.5の段階3と同じ）。
    段階3：それでも超える場合は末尾を切り詰める（build_simpleと同じフェイルセーフ。固定変数
           自体が極端に大きい場合のみ到達する想定）。
    """
    recent_logs = list(context.recent_logs)
    history = list(context.conversation_history)

    def render() -> str:
        variables = dict(context.fixed_variables)
        variables[context.recent_logs_key] = _format_dated_log_entries(
            recent_logs, context.recent_logs_empty_text
        )
        variables["conversation_history"] = format_conversation_history(history)
        return _substitute(template_body, variables)

    text = render()
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)

    was_truncated = False

    # 段階1：直近記録を古い日から除外する。
    while recent_logs and len(text) > max_chars:
        recent_logs.pop(0)
        was_truncated = True
        text = render()

    # 段階2：当日の対話履歴を古い往復から除外する。
    while history and len(text) > max_chars:
        history.pop(0)
        was_truncated = True
        text = render()

    # 段階3：フェイルセーフ（末尾切り詰め）。
    if len(text) > max_chars:
        was_truncated = True
        text = text[:max_chars]

    return BuildResult(text=text, prompt_chars=len(text), was_truncated=was_truncated)


def build_simple(template_body: str, variables: dict[str, str], max_chars: int) -> BuildResult:
    """WEEKLY_SUMMARY・DAILY_MESSAGE・月次報告/半期評価など、縮退段階が定義されていない
    用途向けの単純組み立て。

    上限を超える場合は末尾を切り詰める（情報量が少なく実運用では到達しない想定のフェイルセーフ。
    DAILY_FEEDBACK_READING・DAILY_FEEDBACK_WORKは段階的縮退が必要なためbuild_recent_log_feedback
    を使う。本関数を使い続けるのは、この段階的縮退の対象にならない用途のみ）。
    """
    text = _substitute(template_body, variables)
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)
    return BuildResult(text=text[:max_chars], prompt_chars=max_chars, was_truncated=True)
