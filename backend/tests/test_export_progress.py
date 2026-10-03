"""export_progress のテスト（実装フェーズ分割計画書Phase10注意点
「匿名化時の再生成は複数回のAI呼び出しを伴う。呼び出し間隔の下限を守り、進捗を
表示すること」）。
"""

from app.services import export_progress


def test_get_returns_none_when_not_started():
    assert export_progress.get(999) is None


def test_start_initializes_progress_at_zero():
    export_progress.start(1, total=3)
    try:
        progress = export_progress.get(1)
        assert progress is not None
        assert progress.completed == 0
        assert progress.total == 3
    finally:
        export_progress.finish(1)


def test_advance_increments_completed_without_changing_total():
    export_progress.start(2, total=3)
    try:
        export_progress.advance(2)
        export_progress.advance(2)
        progress = export_progress.get(2)
        assert progress.completed == 2
        assert progress.total == 3
    finally:
        export_progress.finish(2)


def test_advance_before_start_is_a_no_op():
    export_progress.advance(3)
    assert export_progress.get(3) is None


def test_finish_removes_progress():
    export_progress.start(4, total=1)
    export_progress.finish(4)
    assert export_progress.get(4) is None


def test_progress_is_isolated_per_goal_id():
    export_progress.start(5, total=2)
    export_progress.start(6, total=5)
    try:
        export_progress.advance(5)
        assert export_progress.get(5).completed == 1
        assert export_progress.get(6).completed == 0
    finally:
        export_progress.finish(5)
        export_progress.finish(6)
