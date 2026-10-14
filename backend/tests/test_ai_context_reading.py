"""ai_context_reading のテスト（読書目標、ロジック・プロンプト編17.6〜17.7・17.11、
実装フェーズ分割計画書Phase16・S01）。共通処理のテストは`test_ai_context_common.py`を参照。

どのAIプロンプトへ渡す文言もPhase2〜4の既存算出ロジックの組み合わせであるため、
ここでは「必要な情報が文言に含まれているか」を中心に検証し、算出式自体の正しさは
各サービスの既存テスト（test_speed_service.py等）に委ねる（DRYの原則）。
"""

import datetime as dt

from app.constants.enums import RecordState
from app.models.record import DailyRecord, ReadingLog
from app.services import ai_context_reading
from app.services.record_service_reading import ReadingLogItem
from tests import ai_context_helpers, reading_helpers


def _make_goal(session, name="目標A"):
    return ai_context_helpers.make_goal(session, name=name)


def _make_reading_goal(session, name="読書目標A"):
    return reading_helpers.make_reading_goal(session, name=name)


def _make_book(session, goal, **overrides):
    return reading_helpers.make_book(session, goal.id, **overrides)


def _add_reading_log(session, book_id, record_date, **overrides):
    record = DailyRecord(record_date=record_date, reading_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    defaults = dict(daily_record_id=record.id, book_id=book_id, recall_body="想起本文")
    defaults.update(overrides)
    session.add(ReadingLog(**defaults))
    session.flush()


# --- list_active_reading_goals / list_active_books ---


def test_list_active_reading_goals_excludes_exam_goals(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    reading_goal = _make_reading_goal(seeded_session)

    active = ai_context_reading.list_active_reading_goals(seeded_session)

    assert reading_goal.id in {g.id for g in active}
    assert exam_goal.id not in {g.id for g in active}


def test_list_active_books_returns_book_of_each_goal(seeded_session):
    goal_with_book = _make_reading_goal(seeded_session, name="読書目標A")
    book = _make_book(seeded_session, goal_with_book)
    goal_without_book = _make_reading_goal(seeded_session, name="読書目標B")

    books = ai_context_reading.list_active_books([goal_with_book, goal_without_book])

    assert books == [book]


# --- build_daily_book_summary_text ---


def test_build_daily_book_summary_text_includes_title_and_remaining_days(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="達人プログラマー", due_date=dt.date(2026, 1, 20))

    text = ai_context_reading.build_daily_book_summary_text([book], dt.date(2026, 1, 10))

    assert "達人プログラマー" in text
    assert "残り10日" in text


def test_build_daily_book_summary_text_handles_no_books(seeded_session):
    text = ai_context_reading.build_daily_book_summary_text([], dt.date(2026, 1, 10))
    assert "進行中の読書目標はありません" in text


# --- build_today_recall_text ---


def test_build_today_recall_text_includes_book_title_and_recall_body(seeded_session):
    """ページに関する数値は注入しない（仕様変更2026-09-11）。読書の日次報告は評価の場では
    ないため、プロンプト本文の「ページ数や読了ペースを評価しないでください」（ロジック・プロンプト編17.6）と
    矛盾しないよう、現在ページは画面表示専用とし文脈からも外す。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="達人プログラマー")
    item = ReadingLogItem(book_id=book.id, recall_body="DRY原則の話が印象的だった", current_page=20)

    text = ai_context_reading.build_today_recall_text([item], {book.id: book})

    assert text == "■ 達人プログラマー\nDRY原則の話が印象的だった"


def test_build_today_recall_text_handles_no_items():
    text = ai_context_reading.build_today_recall_text([], {})
    assert "本日の想起入力はまだありません" in text


# --- build_recent_recalls_entries ---


def test_build_recent_recalls_entries_excludes_entries_outside_window(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="窓内の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2025, 12, 1), recall_body="窓外の記録")

    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert any("窓内の記録" in text for text in texts)
    assert not any("窓外の記録" in text for text in texts)


def test_build_recent_recalls_entries_excludes_todays_own_record(seeded_session):
    """対象日（today）自身の想起記録は含めない。todayの分は{{today_recall}}で別途渡す
    ため、含めると二重にプロンプトへ注入される不具合になる（2026-09-15是正）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10), recall_body="本日分の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="前日分の記録")

    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert not any("本日分の記録" in text for text in texts)
    assert any("前日分の記録" in text for text in texts)


def test_build_recent_recalls_entries_window_covers_recent_days_count_ending_yesterday(
    seeded_session,
):
    """todayを除外する分、窓をtoday-recent_days〜today-1へ後ろへずらし、実質的な日数
    （recent_days）を変えない（2026-09-15是正）。recent_days=3・today=2026-1-10なら
    2026-1-7〜2026-1-9の3日分が対象。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 7), recall_body="窓の始点")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 6), recall_body="窓の1日外側")

    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=3
    )

    texts = [entry.text for entry in entries]
    assert any("窓の始点" in text for text in texts)
    assert not any("窓の1日外側" in text for text in texts)


def test_build_recent_recalls_entries_orders_oldest_first(seeded_session):
    # build_with_degradable_entriesの段階（古い日から除外）はリスト先頭を古い順と
    # 前提しているため、record_dateの昇順で返ることを固定する（16.5・21.4）。
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="新しい記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 8), recall_body="古い記録")

    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 8), dt.date(2026, 1, 9)]


def test_build_recent_recalls_entries_handles_no_books(seeded_session):
    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [], dt.date(2026, 1, 10), recent_days=14
    )
    assert entries == []


def test_build_recent_recalls_entries_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")

    entries = ai_context_reading.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    assert entries == []


# --- build_retrospective_book_summary_text / build_reading_overall_metrics_text /
# --- build_reading_logs_entries ---


def test_build_retrospective_book_summary_text_includes_period(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(
        seeded_session,
        goal,
        title="達人プログラマー",
        author="デイブトーマス",
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 3, 1),
    )

    text = ai_context_reading.build_retrospective_book_summary_text(book)

    assert "達人プログラマー" in text
    assert "デイブトーマス" in text
    assert "2026-01-01" in text and "2026-03-01" in text


def test_build_reading_overall_metrics_text_computes_max_streak(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    # 1/1〜1/3が3日連続、1/10が単発（最長は3日）。
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 2))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 3))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10))

    text = ai_context_reading.build_reading_overall_metrics_text(seeded_session, book)

    assert "記録日数: 4日" in text
    assert "最長連続記録日数: 3日" in text


def test_build_reading_logs_entries_orders_chronologically(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 2), recall_body="2日目の想起")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1), recall_body="1日目の想起")

    entries = ai_context_reading.build_reading_logs_entries(seeded_session, book)

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 1), dt.date(2026, 1, 2)]


def test_build_reading_logs_entries_date_from_excludes_earlier_entries(seeded_session):
    """L-11: 週次要約で既に圧縮済みの範囲を除外するため、date_from以降のみに絞れること。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1), recall_body="圧縮済みの想起")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10), recall_body="未圧縮の想起")

    entries = ai_context_reading.build_reading_logs_entries(
        seeded_session, book, date_from=dt.date(2026, 1, 5)
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 10)]


def test_build_reading_logs_entries_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)

    entries = ai_context_reading.build_reading_logs_entries(seeded_session, book)

    assert entries == []


# --- build_week_recalls_text ---


def test_build_week_recalls_text_lists_entries_within_range(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="窓内の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 20), recall_body="窓外の記録")

    text = ai_context_reading.build_week_recalls_text(
        seeded_session, book, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "窓内の記録" in text
    assert "窓外の記録" not in text


def test_build_week_recalls_text_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)

    text = ai_context_reading.build_week_recalls_text(
        seeded_session, book, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "この週の想起記録はありません" in text
