"""平文トークン→保存用ハッシュの変換（session_service.py・token_service.pyの共通処理）。

CODING_RULES.md「①DRYの原則」に従い1箇所へ集約する（dry-reviewerレビュー2026-11-28指摘。
両モジュールに同一実装の`_hash_token`が存在していた）。将来`share_link.token_hash`
（D-11、単位1ではテーブル設計のみ先行）を実装する際もこの関数を使う想定。
"""

import hashlib


def hash_token(raw_token: str) -> str:
    """平文トークンのSHA-256ハッシュ（16進64文字）を返す。DBへの保存・検索はこの値を使う。"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
