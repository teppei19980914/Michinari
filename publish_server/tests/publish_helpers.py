"""単位2テストの共通ヘルパー（CODING_RULES.md DRYの原則。test_publish_api.py・
test_view_api.py・test_quiz_answer_api.pyで共通利用する）。
"""

from app.constants.security import CSRF_HEADER_NAME

DEFAULT_PASSWORD = "correct-horse-battery"


def create_and_login(client, username: str, password: str = DEFAULT_PASSWORD) -> str:
    """アカウントを作成しログインする。CSRFトークンを返す（Cookieはclientに保持される）。"""
    create_response = client.post(
        "/api/v1/auth/account", json={"username": username, "password": password}
    )
    assert create_response.status_code == 201, create_response.text

    login_response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["csrf_token"]


def issue_api_token(client, csrf_token: str) -> str:
    """ログイン中のアカウントに紐づくAPIトークン（平文）を発行する。"""
    response = client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: csrf_token})
    assert response.status_code == 201, response.text
    return response.json()["token"]


def bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def gantt_payload(goal_name: str = "資格A") -> dict:
    return {
        "goal_name": goal_name,
        "items": [
            {
                "local_item_id": 1,
                "title": "第1章",
                "description": "重要",
                "planned_start_date": "2026-01-01",
                "planned_end_date": "2026-01-10",
                "status": "NOT_STARTED",
                "actual_start_date": None,
                "actual_end_date": None,
                "display_order": 0,
            }
        ],
        "columns": [
            {"local_column_id": 1, "name": "メモ", "column_type": "TEXT", "display_order": 0}
        ],
        "cells": [{"local_item_id": 1, "local_column_id": 1, "value": "進捗良好"}],
    }


def vocab_payload(deck_name: str = "英単語") -> dict:
    return {
        "deck_name": deck_name,
        "cards": [
            {
                "local_card_id": 1,
                "card_type": "TERM",
                "term": "apple",
                "meaning": "りんご",
                "aliases": None,
                "note": None,
                "situation_text": None,
                "question_text": None,
                "display_order": 0,
            }
        ],
    }


def quiz_payload(
    local_question_id: int = 1, correct_choice_index: int = 0, local_card_id: int = 1
) -> dict:
    """`local_card_id`の既定値（1）は`vocab_payload()`のカード（`local_card_id=1`）に合わせる
    （`replace_quiz_questions`の出所検証、D-03・STRIDE対策）。"""
    return {
        "questions": [
            {
                "local_question_id": local_question_id,
                "local_card_id": local_card_id,
                "question_text": "appleの意味は？",
                "choice_1": "りんご",
                "choice_2": "バナナ",
                "choice_3": "みかん",
                "choice_4": "ぶどう",
                "correct_choice_index": correct_choice_index,
                "explanation": "appleはりんごです。",
            }
        ]
    }


def publish_full_set(client, token: str, local_goal_id: int = 1, local_deck_id: int = 1) -> None:
    """ガント・単語帳・問題をまとめて公開する（正常系テストの前提セットアップ用）。"""
    headers = bearer_header(token)
    assert (
        client.put(f"/api/v1/publish/gantt/{local_goal_id}", json=gantt_payload(), headers=headers)
    ).status_code == 204
    assert (
        client.put(f"/api/v1/publish/vocab/{local_deck_id}", json=vocab_payload(), headers=headers)
    ).status_code == 204
    assert (
        client.put(f"/api/v1/publish/quiz/{local_deck_id}", json=quiz_payload(), headers=headers)
    ).status_code == 204
