import type {
  GoalScheduleItemsForReportRead,
  ScheduleItemUpdateInput,
} from '../../api/records'
import type { components } from '../../types/api.d.ts'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

/**
 * 「今日の作業項目」欄（開発Todo_スケジュール・ガントチャート_v1.1 第4章、単位4）の
 * 1行分の下書き。studyLogForm.ts等と同じ「id（schedule_item_id）ごとの入力値」の形を取る。
 *
 * touchedは、利用者がその行を変更したか（状況の変更・実績日の手入力）を表す。確定・登録時に
 * 送信するのは変更した行だけとする（本書4章「変更しなかった行は送信しない」）ため、
 * 他の実績入力（studyLogValues等、未入力かどうかで送信対象を判定する）とは異なり、
 * 専用のフラグで判定する（作業項目は「既存の値を変更しない」ことと「空にする」ことを
 * 区別する必要があるため、未入力判定では代用できない）。
 */
export type ScheduleItemDraftValue = {
  status: ScheduleItemStatus
  actualStartDate: string | null
  actualEndDate: string | null
  touched: boolean
}

/** 取得結果（目標ごとの作業項目一覧）から下書きの初期値を組み立てる。
 * useDailyReportDraftのhydrate（初回）とマージ（hydrate後の差分反映）の両方から呼ばれる
 * （computeIncomingDraftValuesと同じ方針、CODING_RULES.md「①DRYの原則」）。 */
export function initScheduleItemDraftValues(
  goals: GoalScheduleItemsForReportRead[],
): Record<number, ScheduleItemDraftValue> {
  const result: Record<number, ScheduleItemDraftValue> = {}
  for (const goal of goals) {
    for (const item of goal.items) {
      result[item.id] = {
        status: item.status,
        actualStartDate: item.actual_start_date,
        actualEndDate: item.actual_end_date,
        touched: false,
      }
    }
  }
  return result
}

/** 対象の目標群に属する作業項目idの集合を求める（確定APIごとに送信対象を絞り込むために
 * 使う。確定API3本は種別に属する行だけを受け付けるため、下書き全体〈全カテゴリ分〉から
 * 対象カテゴリの分だけを抜き出す）。 */
export function selectScheduleItemIdsForGoals(
  goals: GoalScheduleItemsForReportRead[],
  goalIds: ReadonlySet<number>,
): Set<number> {
  const ids = new Set<number>()
  for (const goal of goals) {
    if (!goalIds.has(goal.goal_id)) continue
    for (const item of goal.items) {
      ids.add(item.id)
    }
  }
  return ids
}

/** 取得結果に含まれるすべての作業項目idを返す（進捗のみ登録で使う。D-36により確定状態に
 * 関わらずどの種別の行も受け付けるため、カテゴリによる絞り込みを行わない）。 */
export function collectAllScheduleItemIds(
  goals: GoalScheduleItemsForReportRead[],
): Set<number> {
  const ids = new Set<number>()
  for (const goal of goals) {
    for (const item of goal.items) {
      ids.add(item.id)
    }
  }
  return ids
}

/** 変更された行だけを送信用ペイロードへ組み立てる（本書4章「変更しなかった行は送信しない」）。
 * `eligibleItemIds`に無いidは対象外とする（他カテゴリ・他目標の行を誤って送らないため）。 */
export function buildScheduleItemUpdatesPayload(
  values: Record<number, ScheduleItemDraftValue>,
  eligibleItemIds: ReadonlySet<number>,
): ScheduleItemUpdateInput[] {
  return Object.entries(values)
    .filter(([id, value]) => value.touched && eligibleItemIds.has(Number(id)))
    .map(([id, value]) => ({
      schedule_item_id: Number(id),
      status: value.status,
      actual_start_date: value.actualStartDate,
      actual_end_date: value.actualEndDate,
    }))
}
