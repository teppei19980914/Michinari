"""プロンプト組み立てと段階的縮退（設計書 ロジック・プロンプト編16.5、17章）。

プロンプト文面は prompt_template テーブルから読む（呼び出し側の責務）。本モジュールは
テンプレート本文と変数を受け取り、`{{変数名}}` を置換したうえで、文字数が閾値を超える
場合に16.5の4段階で縮退する、純粋な文字列組み立てのみを担う（業務判断=どの値を変数に
渡すかはservices層の責務、データ構造編8.1）。
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


def _format_conversation_history(turns: list[ChatTurn]) -> str:
    if not turns:
        return _NO_CONVERSATION_TEXT
    return "\n".join(f"【{_CHAT_ROLE_LABELS[turn.role]}】{turn.content}" for turn in turns)


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
            "conversation_history": _format_conversation_history(history),
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


def build_simple(template_body: str, variables: dict[str, str], max_chars: int) -> BuildResult:
    """WEEKLY_SUMMARY・DAILY_MESSAGEなど、縮退段階が定義されていない用途向けの単純組み立て。

    上限を超える場合は末尾を切り詰める（情報量が少なく実運用では到達しない想定のフェイルセーフ）。
    """
    text = _substitute(template_body, variables)
    if len(text) <= max_chars:
        return BuildResult(text=text, prompt_chars=len(text), was_truncated=False)
    return BuildResult(text=text[:max_chars], prompt_chars=max_chars, was_truncated=True)
