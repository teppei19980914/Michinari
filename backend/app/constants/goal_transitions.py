"""目標の操作ごとに許可される状態の一覧（遷移表の単一の定義、開発Todo 5-2）。

サービス層（goal_service）はこの表を参照して操作の可否を判定する。API・画面の出し分けも
同じ判定に揃えること（判定を複数箇所に書かない、CLAUDE.md DRYの原則）。

アーカイブは状態列ではなくフラグ（archived_at）のため、ここでは扱わない（アーカイブ中の
状態変更の禁止は goal_service 側で別途検査する）。
"""

import enum

from app.constants.enums import GoalStatus


class GoalOperation(enum.StrEnum):
    """目標に対する状態遷移・削除の操作（画面の名称と対応する）。"""

    #: 開始（下書き → 実行中）。
    ACTIVATE = "ACTIVATE"
    #: 一時停止（実行中 → 一時停止）。
    PAUSE = "PAUSE"
    #: 再開（一時停止・中断・完了 → 実行中）。
    RESUME = "RESUME"
    #: 中断（実行中・一時停止 → 中断）。
    ABANDON = "ABANDON"
    #: 完了（実行中 → 完了）。
    COMPLETE = "COMPLETE"
    #: 実績・日記・コメントの登録・修正・削除（実行中のみ）。
    RECORD = "RECORD"
    #: アーカイブ（実行中以外。下書きからも可）。
    ARCHIVE = "ARCHIVE"
    #: 物理削除（実行中以外のすべて。アーカイブ済みも対象）。
    DELETE = "DELETE"
    #: アーカイブの解除（状態は変えない）。遷移表ではなくアーカイブフラグで判定する。
    UNARCHIVE = "UNARCHIVE"


#: 目標の画面操作として提示する操作（記録・アーカイブ解除を除く。提示順＝画面の並び順）。
USER_FACING_OPERATIONS: tuple[GoalOperation, ...] = (
    GoalOperation.ACTIVATE,
    GoalOperation.PAUSE,
    GoalOperation.RESUME,
    GoalOperation.COMPLETE,
    GoalOperation.ABANDON,
    GoalOperation.ARCHIVE,
    GoalOperation.DELETE,
)


_OPERATION_ALLOWED_STATUSES: dict[GoalOperation, frozenset[GoalStatus]] = {
    GoalOperation.ACTIVATE: frozenset({GoalStatus.DRAFT}),
    GoalOperation.PAUSE: frozenset({GoalStatus.ACTIVE}),
    GoalOperation.RESUME: frozenset(
        {GoalStatus.PAUSED, GoalStatus.CLOSED_WITHOUT_RESULT, GoalStatus.CLOSED_WITH_RESULT}
    ),
    GoalOperation.ABANDON: frozenset({GoalStatus.ACTIVE, GoalStatus.PAUSED}),
    GoalOperation.COMPLETE: frozenset({GoalStatus.ACTIVE}),
    GoalOperation.RECORD: frozenset({GoalStatus.ACTIVE}),
    GoalOperation.ARCHIVE: frozenset(
        {
            GoalStatus.DRAFT,
            GoalStatus.PAUSED,
            GoalStatus.CLOSED_WITHOUT_RESULT,
            GoalStatus.CLOSED_WITH_RESULT,
        }
    ),
    GoalOperation.DELETE: frozenset(
        {
            GoalStatus.DRAFT,
            GoalStatus.PAUSED,
            GoalStatus.CLOSED_WITHOUT_RESULT,
            GoalStatus.CLOSED_WITH_RESULT,
        }
    ),
    # アーカイブ解除は状態に依存しない（アーカイブフラグで判定する。available_operations参照）。
    GoalOperation.UNARCHIVE: frozenset(GoalStatus),
}


def is_operation_allowed(operation: GoalOperation, status: GoalStatus) -> bool:
    """指定の状態で、その操作が許可されるか。"""
    return status in _OPERATION_ALLOWED_STATUSES[operation]


#: 報告を求めない状態（開発Todo 1-6）。この状態の期間は報告率・連続報告日数の分母・判定から除く。
#: 完了（CLOSED_WITH_RESULT）は含めない（完了後の扱いは設計資料で定めていない、未決事項）。
NON_REPORTING_STATUSES: frozenset[GoalStatus] = frozenset(
    {GoalStatus.PAUSED, GoalStatus.CLOSED_WITHOUT_RESULT}
)


#: 再開時の警告コード（資格試験）。画面の文言は ja.json の resumeWarnings.<コード> が持つ。
RESUME_WARNING_QUOTA_INCREASED = "QUOTA_INCREASED"
