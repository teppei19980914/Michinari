"""全モデルをここでインポートし、Base.metadataを確定させる（backend/app/models/__init__.pyと同じ方針）。"""

from app.models.account import PublishAccount
from app.models.base import Base
from app.models.quiz_answer_record import QuizAnswerRecord
from app.models.session import PublishSession
from app.models.share_link import ShareLink
from app.models.snapshot_gantt import PublishedGanttSnapshot
from app.models.snapshot_quiz import PublishedQuizQuestion
from app.models.snapshot_vocab import PublishedVocabDeck
from app.models.token import PublishApiToken

__all__ = [
    "Base",
    "PublishAccount",
    "PublishApiToken",
    "PublishSession",
    "PublishedGanttSnapshot",
    "PublishedQuizQuestion",
    "PublishedVocabDeck",
    "QuizAnswerRecord",
    "ShareLink",
]
