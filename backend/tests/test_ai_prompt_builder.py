"""ai/prompt_builder のテスト（ロジック・プロンプト編16.5の4段階縮退、
読書・仕事の段階的縮退（build_recent_log_feedback）、実装フェーズ分割計画書Phase5）。
"""

import datetime as dt

from app.ai import prompt_builder
from app.ai.prompt_builder import (
    ChatTurn,
    DailyFeedbackContext,
    DatedLogEntry,
    MaterialStatusEntry,
    RecentLogFeedbackContext,
)
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


_RECENT_LOG_TEMPLATE = (
    "固定:{{today}} {{summary}}\n直近:{{recent_recalls}}\n対話:{{conversation_history}}"
)


def _recent_log_context(**overrides) -> RecentLogFeedbackContext:
    defaults = dict(
        fixed_variables={"today": "2026-08-24", "summary": "書籍A"},
        recent_logs=[],
        recent_logs_key="recent_recalls",
        recent_logs_empty_text="（直近の想起記録はありません）",
        conversation_history=[],
    )
    defaults.update(overrides)
    return RecentLogFeedbackContext(**defaults)


def test_build_recent_log_feedback_returns_full_text_when_under_limit():
    result = prompt_builder.build_recent_log_feedback(
        _RECENT_LOG_TEMPLATE, _recent_log_context(), max_chars=100000
    )

    assert result.was_truncated is False
    assert result.prompt_chars == len(result.text)
    assert "書籍A" in result.text


def test_build_recent_log_feedback_substitutes_fixed_variables_and_recent_logs():
    context = _recent_log_context(
        recent_logs=[
            DatedLogEntry(record_date=dt.date(2026, 1, 9), label="書籍A", body="窓内の記録"),
        ],
        conversation_history=[
            ChatTurn(role=ChatRole.USER, content="質問です"),
            ChatTurn(role=ChatRole.ASSISTANT, content="回答です"),
        ],
    )
    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, 100000)

    assert "【2026-01-09 書籍A】" in result.text
    assert "窓内の記録" in result.text
    assert "【学習者】質問です" in result.text
    assert "【AI】回答です" in result.text


def test_build_recent_log_feedback_empty_recent_logs_uses_empty_text():
    result = prompt_builder.build_recent_log_feedback(
        _RECENT_LOG_TEMPLATE, _recent_log_context(), max_chars=100000
    )

    assert "（直近の想起記録はありません）" in result.text


def test_build_recent_log_feedback_stage1_drops_oldest_recent_log_first():
    logs = [
        DatedLogEntry(record_date=dt.date(2026, 1, 8), label="書籍A", body="古い記録" * 50),
        DatedLogEntry(record_date=dt.date(2026, 1, 9), label="書籍A", body="新しい記録" * 50),
    ]
    context = _recent_log_context(recent_logs=logs)
    full_text_len = len(
        prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, 10**9).text
    )
    threshold = full_text_len - 100  # 1件除けば収まるがフルでは収まらない閾値

    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, threshold)

    assert result.was_truncated is True
    assert "新しい記録" in result.text
    assert "古い記録" not in result.text


def test_build_recent_log_feedback_stage1_can_drop_all_recent_logs():
    # weekly_summaries（build_daily_feedback）と異なり「最低1件残す」制約は無い。
    # 対話履歴で削れる余地が無い場合、直近記録が0件まで縮退することを確認する。
    logs = [
        DatedLogEntry(record_date=dt.date(2026, 1, 8), label="書籍A", body="記録A" * 500),
        DatedLogEntry(record_date=dt.date(2026, 1, 9), label="書籍A", body="記録B" * 500),
    ]
    context = _recent_log_context(recent_logs=logs)

    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, max_chars=60)

    assert result.was_truncated is True
    assert "（直近の想起記録はありません）" in result.text
    assert "記録A" not in result.text
    assert "記録B" not in result.text


def test_build_recent_log_feedback_stage2_drops_oldest_conversation_turn_first():
    # recent_logsは空にし、段階1が既に済んだ状態（＝段階2単独の挙動）を検証する
    # （build_daily_feedbackのstage3テストと同じ、他段階を空にして切り分ける手法）。
    history = [
        ChatTurn(role=ChatRole.USER, content="古い質問" * 50),
        ChatTurn(role=ChatRole.ASSISTANT, content="新しい回答" * 50),
    ]
    context = _recent_log_context(conversation_history=history)
    full_len = len(
        prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, 10**9).text
    )

    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, full_len - 50)

    assert "新しい回答" in result.text
    assert "古い質問" not in result.text
    assert result.was_truncated is True


def test_build_recent_log_feedback_stage1_exhausts_recent_logs_before_stage2_starts():
    # 直近記録・対話履歴の双方が縮退対象になる場合、段階1（直近記録）が尽きるまで
    # 段階2（対話履歴）は着手しない（過去の記録から先に削る、という優先順位の検証）。
    logs = [DatedLogEntry(record_date=dt.date(2026, 1, 9), label="書籍A", body="直近の記録")]
    history = [
        ChatTurn(role=ChatRole.USER, content="古い質問" * 50),
        ChatTurn(role=ChatRole.ASSISTANT, content="新しい回答" * 50),
    ]
    context = _recent_log_context(recent_logs=logs, conversation_history=history)

    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, max_chars=120)

    assert "直近の記録" not in result.text  # 段階1で先に除外される
    assert "（直近の想起記録はありません）" in result.text
    assert result.was_truncated is True


def test_build_recent_log_feedback_stage3_fallback_trims_tail_when_fixed_variables_alone_exceed():
    # recent_logs・conversation_historyを使い切っても固定変数自体が閾値を超える状況
    # （段階3の末尾切り詰めフェイルセーフに到達することを確認する）。
    context = _recent_log_context(fixed_variables={"today": "2026-08-24", "summary": "A" * 200})

    result = prompt_builder.build_recent_log_feedback(_RECENT_LOG_TEMPLATE, context, max_chars=50)

    assert len(result.text) == 50
    assert result.was_truncated is True


def test_build_simple_returns_full_text_when_under_limit():
    result = prompt_builder.build_simple("こんにちは{{name}}", {"name": "太郎"}, max_chars=100)

    assert result.text == "こんにちは太郎"
    assert result.was_truncated is False


def test_build_simple_truncates_when_over_limit():
    result = prompt_builder.build_simple("{{name}}", {"name": "あ" * 100}, max_chars=10)

    assert len(result.text) == 10
    assert result.was_truncated is True
