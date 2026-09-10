import type { SlotAllocationRead } from '../../api/goals'

/** リソース配分タブの入力状態（slot_id → 分の文字列。送信直前に数値へ変換する）。 */
export type SlotAllocationFormValues = Record<number, string>

/** 入力欄の初期値を組み立てる（0分の枠は空欄として表示する）。 */
export function initSlotAllocationValues(rows: SlotAllocationRead[]): SlotAllocationFormValues {
  const values: SlotAllocationFormValues = {}
  for (const row of rows) {
    values[row.slot_id] = row.minutes === 0 ? '' : String(row.minutes)
  }
  return values
}

/** 入力値を分へ解釈する（空欄・非数値は0分として扱う）。 */
export function parseMinutes(value: string | undefined): number {
  const trimmed = (value ?? '').trim()
  if (trimmed === '') {
    return 0
  }
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0
}

/**
 * 1行分の空き時間（分）。
 * 他目標の配分を除いた残りであり、自分の入力分は含めない（入力の上限の目安として表示する）。
 */
export function freeMinutes(row: SlotAllocationRead): number {
  return row.duration_minutes - row.others_minutes
}

/** 入力値がその枠の空き時間を超えているか（保存はサーバ側で拒否される。仕様書NT-04）。 */
export function exceedsFreeMinutes(row: SlotAllocationRead, value: string | undefined): boolean {
  return parseMinutes(value) > freeMinutes(row)
}

/** 配分時間の合計（週あたりの確保時間として画面に表示する）。 */
export function totalMinutes(values: SlotAllocationFormValues): number {
  return Object.values(values).reduce((sum, value) => sum + parseMinutes(value), 0)
}

/** 送信用ペイロードを組み立てる（0分の枠も送り、サーバ側で行を削除させる）。 */
export function buildSlotAllocationPayload(
  rows: SlotAllocationRead[],
  values: SlotAllocationFormValues,
): { allocations: { slot_id: number; minutes: number }[] } {
  return {
    allocations: rows.map((row) => ({
      slot_id: row.slot_id,
      minutes: parseMinutes(values[row.slot_id]),
    })),
  }
}
