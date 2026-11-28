"""app/services/token_hashing.py のテスト（session_service/token_service共通処理）。"""

from app.services.token_hashing import hash_token


def test_hash_token_is_deterministic():
    assert hash_token("same-raw-token") == hash_token("same-raw-token")


def test_hash_token_differs_for_different_input():
    assert hash_token("token-a") != hash_token("token-b")


def test_hash_token_returns_64_char_hex_digest():
    digest = hash_token("any-raw-token")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
