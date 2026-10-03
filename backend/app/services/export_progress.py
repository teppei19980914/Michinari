"""匿名化エクスポート実行中の進捗を保持する（実装フェーズ分割計画書Phase10注意点
「匿名化時の再生成は複数回のAI呼び出しを伴う。呼び出し間隔の下限を守り、進捗を
表示すること」）。

技術選定書 v1.0が想定する単一利用者・ローカル運用のため、ジョブキュー等の外部基盤は
導入せず、プロセス内メモリでgoal_idごとの進捗を保持する単純な実装とする。
"""

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ExportProgress:
    completed: int
    total: int


_lock = Lock()
_progress: dict[int, ExportProgress] = {}


def start(goal_id: int, total: int) -> None:
    """goal_idの進捗をcompleted=0で初期化する。呼び出し元（export_service.execute_export）が
    処理開始前に、想定するステップ総数（total）を渡す。"""
    with _lock:
        _progress[goal_id] = ExportProgress(completed=0, total=total)


def advance(goal_id: int) -> None:
    """goal_idの進捗を1件分進める。start()より前に呼ばれた場合は何もしない
    （進捗表示の対象外の呼び出し経路（テスト等）との整合を保つため）。"""
    with _lock:
        current = _progress.get(goal_id)
        if current is not None:
            _progress[goal_id] = ExportProgress(
                completed=current.completed + 1, total=current.total
            )


def finish(goal_id: int) -> None:
    """goal_idの進捗を破棄する。呼び出し元はtry/finallyで、正常終了・例外時いずれも
    呼び出し、進捗の残留（フロントの無限ポーリング化）を防ぐ。"""
    with _lock:
        _progress.pop(goal_id, None)


def get(goal_id: int) -> ExportProgress | None:
    """goal_idの現在の進捗を返す。進行中でなければNone
    （GET /goals/{goal_id}/knowledge-export/progress が返す in_progress の判定に用いる）。"""
    with _lock:
        return _progress.get(goal_id)
