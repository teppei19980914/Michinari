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


class NotFoundError(DomainError):
    """指定されたIDのエンティティが存在しない場合（API層でNOT_FOUNDへ変換、データ構造編6.3）。"""

    def __init__(self, entity_name: str, entity_id: object) -> None:
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name}(id={entity_id}) が見つかりません")


class ValidationError(DomainError):
    """入力値・状態整合の検証エラー（データ構造編6.3 VALIDATION_ERROR、仕様書10章）。"""


class ExamSubjectRequiredError(DomainError):
    """目標開始に必要な試験科目が1件も登録されていない場合（仕様書7.1）。

    教材未登録・リソース配分未設定と画面上で判別できるよう、VALIDATION_ERRORとは
    別のエラーコードを持つ専用例外とする。
    """

    def __init__(self) -> None:
        super().__init__("試験科目を1件以上登録してください")


class MaterialRequiredError(DomainError):
    """目標開始に必要な教材が1件も登録されていない場合（仕様書7.1）。

    試験科目未登録・リソース配分未設定と画面上で判別できるよう、VALIDATION_ERRORとは
    別のエラーコードを持つ専用例外とする。
    """

    def __init__(self) -> None:
        super().__init__("教材を1件以上登録してください")


class ResourceRatioRequiredError(DomainError):
    """目標の開始・再開時にリソース配分が未設定（0のまま）の場合（仕様書7.1）。

    試験科目未登録・教材未登録と画面上で判別できるよう、VALIDATION_ERRORとは
    別のエラーコードを持つ専用例外とする。
    """

    def __init__(self) -> None:
        super().__init__("リソース配分を設定してください")


class ResourceRatioExceededError(DomainError):
    """ACTIVEな目標のresource_ratio合計が1.0を超える場合（データ構造編5.3、仕様書7.1）。"""

    def __init__(self, total_ratio: float) -> None:
        self.total_ratio = total_ratio
        super().__init__(f"リソース配分の合計が100%を超えます（{total_ratio:.2%}）")


class InvalidStateTransitionError(DomainError):
    """許可されない目標の状態遷移、またはクローズ済み目標への更新（仕様書7.1、6.2）。"""


class MaterialHasStudyLogsError(DomainError):
    """実績（study_log）が存在する教材を削除しようとした場合（データ構造編6.2）。"""

    def __init__(self, material_id: int) -> None:
        self.material_id = material_id
        super().__init__(f"教材(id={material_id})には実績が存在するため削除できません")


class BookHasReadingLogsError(DomainError):
    """想起記録（reading_log）が存在する書籍を削除しようとした場合
    （MaterialHasStudyLogsErrorの読書版、データ構造編6.2）。"""

    def __init__(self, book_id: int) -> None:
        self.book_id = book_id
        super().__init__(f"書籍(id={book_id})には想起記録が存在するため削除できません")


class BookAlreadyExistsError(DomainError):
    """1目標1冊の制約に反して2件目の書籍を登録しようとした場合
    （データ構造編6.3 BOOK_ALREADY_EXISTS、要件定義書R-70）。"""

    def __init__(self, goal_id: int) -> None:
        self.goal_id = goal_id
        super().__init__(f"目標(id={goal_id})には既に書籍が登録されています")


class WorkAssignmentHasWorkLogsError(DomainError):
    """業務記録（work_log）が存在する案件情報を削除しようとした場合
    （BookHasReadingLogsErrorの仕事版、データ構造編6.2）。"""

    def __init__(self, work_assignment_id: int) -> None:
        self.work_assignment_id = work_assignment_id
        super().__init__(f"案件情報(id={work_assignment_id})には業務記録が存在するため削除できません")


class WorkAssignmentAlreadyExistsError(DomainError):
    """1目標1案件の制約に反して2件目の案件情報を登録しようとした場合
    （データ構造編6.3 WORK_ASSIGNMENT_ALREADY_EXISTS、要件定義書R-72）。"""

    def __init__(self, goal_id: int) -> None:
        self.goal_id = goal_id
        super().__init__(f"目標(id={goal_id})には既に案件情報が登録されています")


class ImmutableRecordError(DomainError):
    """確定済み(REPORTED)の日次記録を更新しようとした場合（データ構造編6.3 IMMUTABLE_RECORD）。"""

    def __init__(self, record_date: object) -> None:
        self.record_date = record_date
        super().__init__(f"日付({record_date})の記録は確定済みのため更新できません")


class BackdateLimitExceededError(DomainError):
    """報告確定の遡及入力可能期限（当日または前日）を超えた場合
    （データ構造編6.3 BACKDATE_LIMIT_EXCEEDED、仕様書7.2）。"""

    def __init__(self, record_date: object, today: object) -> None:
        self.record_date = record_date
        self.today = today
        super().__init__(f"日付({record_date})への報告確定は前日までに限られます（本日: {today}）")
