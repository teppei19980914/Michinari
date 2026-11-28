"""アカウント削除時のCASCADE実動作の検証（D-23）。

メタデータ上の`ondelete="CASCADE"`定義（test_migrations.py）だけでなく、実際に
`PRAGMA foreign_keys = ON`（app/database.py）が効いた状態で削除が連鎖することを確認する。
"""

from app.models.account import PublishAccount
from app.models.quiz_answer_record import QuizAnswerRecord
from app.models.session import PublishSession
from app.models.snapshot_gantt import PublishedGanttSnapshot
from app.models.snapshot_quiz import PublishedQuizQuestion
from app.models.snapshot_vocab import PublishedVocabDeck
from app.models.token import PublishApiToken
from app.services import session_service, token_service


def test_deleting_account_cascades_to_tokens_and_sessions(db_session):
    account = PublishAccount(username="cascade_user", password_hash="x")
    db_session.add(account)
    db_session.commit()

    token_service.issue_token(db_session, account)
    session_service.create_session(db_session, account)

    db_session.delete(account)
    db_session.commit()

    assert db_session.query(PublishApiToken).count() == 0
    assert db_session.query(PublishSession).count() == 0


def _create_published_quiz_question(db_session, account: PublishAccount) -> PublishedQuizQuestion:
    deck = PublishedVocabDeck(
        account_id=account.id, local_deck_id=1, deck_name="d", cards_json="[]"
    )
    db_session.add(deck)
    db_session.commit()
    question = PublishedQuizQuestion(
        account_id=account.id,
        vocab_deck_snapshot_id=deck.id,
        local_question_id=1,
        question_text="q",
        choices_json="{}",
        correct_choice_index=0,
        explanation="e",
    )
    db_session.add(question)
    db_session.commit()
    return question


def test_deleting_account_cascades_to_unit2_snapshots_and_answer_records(db_session):
    from app.models.base import utcnow

    account = PublishAccount(username="cascade_user_2", password_hash="x")
    db_session.add(account)
    db_session.commit()

    db_session.add(
        PublishedGanttSnapshot(
            account_id=account.id,
            local_goal_id=1,
            goal_name="g",
            items_json="[]",
            columns_json="[]",
            cells_json="[]",
        )
    )
    question = _create_published_quiz_question(db_session, account)
    db_session.add(
        QuizAnswerRecord(
            account_id=account.id,
            question_id=question.id,
            local_question_id=question.local_question_id,
            chosen_index=0,
            is_correct=True,
            answered_at=utcnow(),
            client_answer_uuid="u1",
        )
    )
    db_session.commit()

    db_session.delete(account)
    db_session.commit()

    assert db_session.query(PublishedGanttSnapshot).count() == 0
    assert db_session.query(PublishedVocabDeck).count() == 0
    assert db_session.query(PublishedQuizQuestion).count() == 0
    assert db_session.query(QuizAnswerRecord).count() == 0


def test_deleting_vocab_deck_cascades_to_quiz_questions(db_session):
    account = PublishAccount(username="cascade_user_3", password_hash="x")
    db_session.add(account)
    db_session.commit()
    question = _create_published_quiz_question(db_session, account)
    deck_id = question.vocab_deck_snapshot_id

    db_session.query(PublishedVocabDeck).filter(PublishedVocabDeck.id == deck_id).delete()
    db_session.commit()

    assert db_session.query(PublishedQuizQuestion).count() == 0


def test_deleting_quiz_question_sets_answer_record_question_id_to_null(db_session):
    from app.models.base import utcnow

    account = PublishAccount(username="cascade_user_4", password_hash="x")
    db_session.add(account)
    db_session.commit()
    question = _create_published_quiz_question(db_session, account)
    db_session.add(
        QuizAnswerRecord(
            account_id=account.id,
            question_id=question.id,
            local_question_id=question.local_question_id,
            chosen_index=0,
            is_correct=True,
            answered_at=utcnow(),
            client_answer_uuid="u2",
        )
    )
    db_session.commit()

    db_session.query(PublishedQuizQuestion).filter(PublishedQuizQuestion.id == question.id).delete()
    db_session.commit()

    record = db_session.query(QuizAnswerRecord).filter_by(client_answer_uuid="u2").one()
    assert record.question_id is None
    # ローカル取込（単位5）時の照合キーは残り続ける（6.1節）。
    assert record.local_question_id == question.local_question_id
