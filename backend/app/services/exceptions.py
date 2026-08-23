"""サービス層のドメイン例外。

CLAUDE.md「サービス層でのHTTP例外の送出」禁止に従い、HTTPExceptionではなくここに定義する
ドメイン例外を送出する。HTTPステータスへの変換はAPI層（Phase3以降）で行う。
"""


class DomainError(Exception):
    """サービス層が送出する例外の基底クラス。"""


class AppSettingNotFoundError(DomainError):
    """参照した app_setting.key が存在しない場合（初期投入漏れ・キー誤りを示す）。"""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"app_setting に key='{key}' が存在しません")


class PlannedCyclesBelowCompletedError(DomainError):
    """予定周回数を、既に完了した周回数未満へ変更しようとした場合（ロジック・プロンプト編 6.4）。"""

    def __init__(self, current_cycle: int, new_planned_cycles: int) -> None:
        self.current_cycle = current_cycle
        self.new_planned_cycles = new_planned_cycles
        super().__init__(
            f"予定周回数({new_planned_cycles})を現在周回({current_cycle})未満にはできません"
        )
