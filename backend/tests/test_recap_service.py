"""振り返り（テーマ別・週またぎ累積）の報告収集・分類結果の取り込みのテスト。"""

import datetime as dt

from sqlalchemy import select

from app.constants.enums import RecapSourceKind
from app.models.recap import RecapEntry, RecapTheme, RecapThemeLink
from app.services import recap_service, record_service
from tests import reading_helpers
from tests.diary_helpers import finalize_diary, make_exam_goal

# --- parse_classification ---


def test_parse_classification_maps_entry_ids_to_theme_names():
    response = "#1: メール関連、認証\n#2: IPアドレス関連"

    result = recap_service.parse_classification(response, {1, 2})

    assert result == {1: ["メール関連", "認証"], 2: ["IPアドレス関連"]}


def test_parse_classification_ignores_unknown_ids_and_malformed_lines():
    response = "#9: 未知の報告\n説明文のみの行\n#1 テーマ区切りがない\n#2: 有効"

    result = recap_service.parse_classification(response, {1, 2})

    assert result == {2: ["有効"]}


def test_parse_classification_drops_lines_with_only_separators():
    assert recap_service.parse_classification("#1: 、、", {1}) == {}


def test_parse_classification_trims_dedupes_and_truncates_names():
    long_name = "あ" * 150
    response = f"#1: 　SMTP , SMTP，{long_name}、、"

    result = recap_service.parse_classification(response, {1})

    assert result == {1: ["SMTP", "あ" * recap_service.THEME_NAME_MAX_LENGTH]}


def test_parse_classification_accepts_fullwidth_colon():
    assert recap_service.parse_classification("#3：DMARC", {3}) == {3: ["DMARC"]}


def test_parse_classification_returns_empty_for_no_matches():
    assert recap_service.parse_classification("", {1}) == {}


# --- collect_pending_entries ---


def test_collect_registers_diary_entries_with_learned_text_and_legacy_body(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTPの役割")
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_body="旧仕様の本文")

    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )

    assert [e.record_date for e in pending] == [dt.date(2026, 3, 9), dt.date(2026, 3, 10)]
    assert {e.source_kind for e in pending} == {RecapSourceKind.DIARY}


def test_collect_skips_empty_diary_and_out_of_range_dates(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="")
    finalize_diary(seeded_session, goal, dt.date(2026, 2, 1), diary_learned="範囲外")

    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )

    assert pending == []


def test_collect_is_idempotent_and_excludes_classified_entries(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="学び")
    start, end = dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    first = recap_service.collect_pending_entries(seeded_session, goal, start, end)
    recap_service.apply_classification(seeded_session, goal, {first[0].id: ["テーマ"]})

    second = recap_service.collect_pending_entries(seeded_session, goal, start, end)

    assert second == []
    assert seeded_session.query(RecapEntry).count() == 1


def test_collect_registers_reading_recall_records(seeded_session):
    goal = reading_helpers.make_reading_goal(seeded_session, name="読書目標")
    book = reading_helpers.make_book(seeded_session, goal.id)
    record_service.finalize_reading_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [reading_helpers.reading_log_item(book.id, recall_body="ネットワークの層")],
        dt.date(2026, 3, 9),
    )

    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )

    assert len(pending) == 1
    assert pending[0].source_kind is RecapSourceKind.READING


# --- entry_texts ---


def test_entry_texts_prefers_learned_text_and_fetches_in_bulk(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(
        seeded_session, goal, dt.date(2026, 3, 9), diary_body="旧", diary_learned="新しい学び"
    )
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_body="旧のみ")
    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )

    texts = recap_service.entry_texts(seeded_session, pending)

    assert [t.text for t in texts] == ["新しい学び", "旧のみ"]


def test_entry_texts_returns_recall_body_for_reading(seeded_session):
    goal = reading_helpers.make_reading_goal(seeded_session, name="読書目標")
    book = reading_helpers.make_book(seeded_session, goal.id)
    record_service.finalize_reading_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [reading_helpers.reading_log_item(book.id, recall_body="想起内容")],
        dt.date(2026, 3, 9),
    )
    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )

    assert recap_service.entry_texts(seeded_session, pending)[0].text == "想起内容"


def test_entry_texts_is_empty_for_no_entries(seeded_session):
    assert recap_service.entry_texts(seeded_session, []) == []


# --- apply_classification ---


def test_apply_creates_themes_and_links_entry_to_multiple_themes(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SPFとDKIM")
    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )
    entry = pending[0]

    touched = recap_service.apply_classification(
        seeded_session, goal, {entry.id: ["メール関連", "認証"]}
    )

    themes = seeded_session.scalars(select(RecapTheme).where(RecapTheme.goal_id == goal.id)).all()
    assert {t.name for t in themes} == {"メール関連", "認証"}
    assert len(touched) == 2
    assert seeded_session.query(RecapThemeLink).count() == 2
    seeded_session.refresh(entry)
    assert entry.classified_at is not None


def test_apply_reuses_existing_theme_name(seeded_session):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPF")
    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )
    recap_service.apply_classification(seeded_session, goal, {pending[0].id: ["メール関連"]})

    touched = recap_service.apply_classification(
        seeded_session, goal, {pending[1].id: ["メール関連"]}
    )

    assert seeded_session.query(RecapTheme).count() == 1
    assert len(touched) == 1
    assert seeded_session.query(RecapThemeLink).count() == 2


def test_apply_ignores_entries_already_classified_or_of_other_goals(seeded_session):
    goal = make_exam_goal(seeded_session)
    other = make_exam_goal(seeded_session, name="別目標")
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="学び")
    pending = recap_service.collect_pending_entries(
        seeded_session, goal, dt.date(2026, 3, 9), dt.date(2026, 3, 15)
    )
    recap_service.apply_classification(seeded_session, goal, {pending[0].id: ["A"]})

    touched = recap_service.apply_classification(seeded_session, other, {pending[0].id: ["B"]})
    again = recap_service.apply_classification(seeded_session, goal, {pending[0].id: ["A"]})

    assert touched == set()
    assert again == set()
    assert seeded_session.query(RecapThemeLink).count() == 1


def _seed_export_themes(session, goal):
    from app.models.recap import RecapTheme

    finalize_diary(session, goal, dt.date(2026, 3, 9), diary_learned="SMTPの役割")
    finalize_diary(session, goal, dt.date(2026, 3, 10), diary_learned="SPFの仕組み")
    pending = recap_service.collect_pending_entries(
        session, goal, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
    )
    recap_service.apply_classification(session, goal, {e.id: ["メール関連"] for e in pending})
    theme = session.query(RecapTheme).filter_by(goal_id=goal.id).one()
    theme.body = "・SMTP（2026-03-09）\n・SPF（2026-03-10）"
    session.commit()


def test_goal_themes_for_export_returns_bodies_with_entries_in_date_order(seeded_session):
    goal = make_exam_goal(seeded_session)
    _seed_export_themes(seeded_session, goal)

    themes = recap_service.goal_themes_for_export(seeded_session, goal)

    assert len(themes) == 1
    assert themes[0]["name"] == "メール関連"
    assert themes[0]["body"].startswith("・SMTP")
    assert [e["record_date"] for e in themes[0]["entries"]] == ["2026-03-09", "2026-03-10"]
    assert themes[0]["entries"][0]["text"] == "SMTPの役割"
    assert themes[0]["entries"][0]["source_kind"] == "DIARY"


def test_goal_themes_for_export_is_empty_without_themes(seeded_session):
    goal = make_exam_goal(seeded_session)

    assert recap_service.goal_themes_for_export(seeded_session, goal) == []


def test_export_includes_recap_themes_unless_anonymized(seeded_session):
    from app.services import export_service

    goal = make_exam_goal(seeded_session)
    _seed_export_themes(seeded_session, goal)
    selection = export_service.ExportSelection(
        goal_overview=False,
        materials=False,
        summary=False,
        daily_records=False,
        quality_trend=False,
        replan_history=False,
        weekly_summaries=False,
        recap_themes=True,
        exam_results=False,
        retrospective=False,
    )

    included = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 3, 20),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    anonymized = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 3, 20),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert included["recap_themes"][0]["name"] == "メール関連"
    assert "recap_themes" not in anonymized


def test_markdown_renders_recap_theme_bodies_or_no_record_message(seeded_session):
    from app.services import export_service

    goal = make_exam_goal(seeded_session)
    _seed_export_themes(seeded_session, goal)
    selection = export_service.ExportSelection(
        goal_overview=False,
        materials=False,
        summary=False,
        daily_records=False,
        quality_trend=False,
        replan_history=False,
        weekly_summaries=False,
        recap_themes=True,
        exam_results=False,
        retrospective=False,
    )
    data = {"recap_themes": recap_service.goal_themes_for_export(seeded_session, goal)}

    markdown = export_service.render_markdown(data, selection)
    empty = export_service.render_markdown({"recap_themes": []}, selection)

    assert "## 8. 振り返りテーマ" in markdown
    assert "### メール関連" in markdown
    assert "・SMTP（2026-03-09）" in markdown
    assert "## 8. 振り返りテーマ" in empty
    assert "（記録なし）" in empty
