"""ai/prompt_builder のテスト（ロジック・プロンプト編16.5の4段階縮退、
実装フェーズ分割計画書Phase5）。
"""

import datetime as dt

from app.ai import prompt_builder
from app.ai.prompt_builder import ChatTurn, DailyFeedbackContext, MaterialStatusEntry
from app.constants.enums import ChatRole

_TEMPLATE = (
    "週次:{{weekly_summaries}}\n"
    "教材:{{material_status}}\n"
    "対話:{{conversation_history}}\n"
    "日記:{{diary_body}}\n"
    "本日:{{today}} {{day_type}} {{load_coefficient}}\n"
    "目標:{{goal_summary}}\n"
    "スロット:{{slot_summary}}\n"
    "バッファ:{{buffer_usage_rate}}\n"
    "実績:{{today_logs}}\n"
    "学び:{{diary_learned}}"
)


def _context(**overrides) -> DailyFeedbackContext:
    defaults = dict(
        today="2026-08-24",
        day_type="PLAN",
        load_coefficient="1.00",
        goal_summary="目標A",
        material_entries=[],
        slot_summary="スロットなし",
        buffer_usage_rate="0%",
        today_logs="実績なし",
        diary_body="",
        diary_learned="",
        weekly_summaries=[],
        conversation_history=[],
    )
    defaults.update(overrides)
    return DailyFeedbackContext(**defaults)


def test_build_daily_feedback_returns_full_text_when_under_limit():
    result = prompt_builder.build_daily_feedback(_TEMPLATE, _context(), max_chars=100000)

    assert result.was_truncated is False
    assert result.prompt_chars == len(result.text)
    assert "目標A" in result.text


def test_build_daily_feedback_substitutes_all_variables():
    context = _context(
        diary_body="今日は頑張った",
        diary_learned="過去問を解いた",
        conversation_history=[
            ChatTurn(role=ChatRole.USER, content="質問です"),
            ChatTurn(role=ChatRole.ASSISTANT, content="回答です"),
        ],
    )
    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, max_chars=100000)

    assert "今日は頑張った" in result.text
    assert "過去問を解いた" in result.text
    assert "【学習者】質問です" in result.text
    assert "【AI】回答です" in result.text


def test_build_daily_feedback_stage1_drops_oldest_weekly_summary_first():
    # 縮退の閾値を、週次要約2件のうち1件を除けば収まる大きさに調整する。
    weekly = ["新しい週の要約" * 50, "古い週の要約" * 50]
    context = _context(weekly_summaries=weekly)
    full_text_len = len(prompt_builder.build_daily_feedback(_TEMPLATE, context, 10**9).text)
    threshold = full_text_len - 100  # 1件除けば収まるがフルでは収まらない閾値

    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, threshold)

    assert result.was_truncated is True
    assert "新しい週の要約" in result.text
    assert "古い週の要約" not in result.text


def test_build_daily_feedback_stage1_keeps_at_least_one_weekly_summary():
    # 2件のうち1件は除去できるが、残り1件だけでも閾値を超え続ける状況を作る
    # （段階2〜4で削れる材料が無いため、最終的に1件を残したまま縮退が止まることを確認する）。
    weekly = ["新しい週の要約" * 1000, "古い週の要約" * 1000]
    context = _context(weekly_summaries=weekly)
    single_summary_context = _context(weekly_summaries=[weekly[0]])
    after_one_removed_len = len(
        prompt_builder.build_daily_feedback(_TEMPLATE, single_summary_context, 10**9).text
    )

    result = prompt_builder.build_daily_feedback(
        _TEMPLATE, context, max_chars=after_one_removed_len - 100
    )

    assert "新しい週の要約" in result.text
    assert "古い週の要約" not in result.text
    assert result.was_truncated is True


def test_build_daily_feedback_stage2_collapses_far_due_material_first():
    near = MaterialStatusEntry(due_date=dt.date(2026, 9, 1), text="近い締切教材" * 30)
    far = MaterialStatusEntry(due_date=dt.date(2027, 3, 1), text="遠い締切教材" * 30)
    context = _context(material_entries=[far, near])
    full_len = len(prompt_builder.build_daily_feedback(_TEMPLATE, context, 10**9).text)

    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, full_len - 50)

    assert "近い締切教材" in result.text
    assert "遠い締切教材" not in result.text
    assert "集約表示" in result.text
    assert result.was_truncated is True


def test_build_daily_feedback_stage3_drops_oldest_conversation_turn_first():
    history = [
        ChatTurn(role=ChatRole.USER, content="古い質問" * 50),
        ChatTurn(role=ChatRole.ASSISTANT, content="新しい回答" * 50),
    ]
    context = _context(conversation_history=history)
    full_len = len(prompt_builder.build_daily_feedback(_TEMPLATE, context, 10**9).text)

    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, full_len - 50)

    assert "新しい回答" in result.text
    assert "古い質問" not in result.text


def test_build_daily_feedback_stage4_trims_diary_from_head_keeping_tail():
    diary = "A" * 500 + "TAIL_KEEP"
    context = _context(diary_body=diary)
    full_len = len(prompt_builder.build_daily_feedback(_TEMPLATE, context, 10**9).text)

    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, full_len - 30)

    assert "TAIL_KEEP" in result.text
    assert "A" * 500 not in result.text
    assert result.was_truncated is True


def test_build_daily_feedback_all_stages_combined_marks_truncated():
    context = _context(
        weekly_summaries=["週1" * 300, "週2" * 300],
        material_entries=[
            MaterialStatusEntry(due_date=dt.date(2026, 9, 1), text="教材A" * 300),
            MaterialStatusEntry(due_date=dt.date(2027, 1, 1), text="教材B" * 300),
        ],
        conversation_history=[
            ChatTurn(role=ChatRole.USER, content="質問" * 300),
            ChatTurn(role=ChatRole.ASSISTANT, content="回答" * 300),
        ],
        diary_body="日記本文" * 300,
    )

    result = prompt_builder.build_daily_feedback(_TEMPLATE, context, max_chars=50)

    assert result.was_truncated is True
    assert result.prompt_chars == len(result.text)


def test_build_simple_returns_full_text_when_under_limit():
    result = prompt_builder.build_simple("こんにちは{{name}}", {"name": "太郎"}, max_chars=100)

    assert result.text == "こんにちは太郎"
    assert result.was_truncated is False


def test_build_simple_truncates_when_over_limit():
    result = prompt_builder.build_simple("{{name}}", {"name": "あ" * 100}, max_chars=10)

    assert len(result.text) == 10
    assert result.was_truncated is True
