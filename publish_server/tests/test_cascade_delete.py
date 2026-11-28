"""アカウント削除時のCASCADE実動作の検証（D-23）。

メタデータ上の`ondelete="CASCADE"`定義（test_migrations.py）だけでなく、実際に
`PRAGMA foreign_keys = ON`（app/database.py）が効いた状態で削除が連鎖することを確認する。
"""

from app.models.account import PublishAccount
from app.models.session import PublishSession
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
