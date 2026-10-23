"""利用者の自由入力をAIへ送る前の安全対策の共通処理（CODING_RULES.md DRYの原則）。

ヘルプAIアシスタント（`help_assistant_service.py`）・目標相談チャット（`goal_consultation_service_common.py`）
など、利用者の自由入力を受け付けてAIへ送る用途で共通する処理をここへ集約する
（S09、両用途で同じ実装だったものを抽出。元はヘルプ側にのみ実装されていた）。
"""

import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.ai import AiForbiddenTerm
from app.services.exceptions import ValidationError

#: 質問を区切りの中へ埋め込む前に、山括弧を全角へ置換する。区切り（`<<<QUESTION-...>>>`）を
#: 利用者の入力から偽造できないようにするため（nonce と併用する二重の防御）。
DELIMITER_REPLACEMENTS = str.maketrans({"<": "＜", ">": "＞"})

#: 照合用の正規化で取り除く対象（空白類）。
WHITESPACE_PATTERN = re.compile(r"\s+")

#: 区切りの乱数のバイト数（`secrets.token_hex` に渡す）。
NONCE_BYTES = 8


def normalize_for_match(text: str) -> str:
    """照合用に正規化する（NFKC・小文字化・空白除去）。

    全角と半角の違い、大文字と小文字の違い、空白の挿入による禁止語の回避を防ぐ。
    """
    return WHITESPACE_PATTERN.sub("", unicodedata.normalize("NFKC", text)).lower()


def contains_forbidden_term(session: Session, text: str) -> bool:
    """有効な禁止語（`ai_forbidden_term`）を含むかを返す（照合は正規化後）。

    禁止語はヘルプAIアシスタント・目標相談チャットで共有する（カテゴリ区別なし、開発Todo U9）。
    語が空の行は照合に使わない。
    """
    normalized = normalize_for_match(text)
    terms = session.query(AiForbiddenTerm).filter(AiForbiddenTerm.enabled.is_(True)).all()
    return any(
        key and key in normalized for key in (normalize_for_match(term.term) for term in terms)
    )


def sanitize_question(raw: str, max_chars: int) -> str:
    """質問を検証して整える。

    制御文字（改行以外）を取り除き、前後の空白を除く。空・上限超過は `ValidationError`。
    上限は呼び出し側が用途別の設定（`ai.help_question_max_chars`／
    `ai.goal_consultation_question_max_chars`等）を読んで渡す。
    """
    cleaned = "".join(ch for ch in raw if ch == "\n" or unicodedata.category(ch) != "Cc").strip()
    if not cleaned:
        raise ValidationError("Question must not be empty")
    if len(cleaned) > max_chars:
        raise ValidationError(f"Question must be {max_chars} characters or fewer")
    return cleaned
