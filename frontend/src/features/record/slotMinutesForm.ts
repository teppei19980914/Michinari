import type { components } from '../../types/api.d.ts'

type SlotDefaultMinutesRead = components['schemas']['SlotDefaultMinutesRead']
type SlotMinutesRead = components['schemas']['SlotMinutesRead']
type SlotMinutesInput = components['schemas']['SlotMinutesInput']

/** 時間枠ごとの投下時間の入力状態（slot_id → 分の文字列）。仕様書6.5。 */
export type SlotMinutesFormValue = Record<number, string>

/** 入力欄として並べる時間枠（配分済みの枠＋利用者が追加した枠）。 */
export type SlotMinutesRow = {
  slotId: number
  slotName: string
}

/**
 * 初期値を組み立てる。既存の実績があればその内訳を優先し、無ければ配分の按分結果
 * （slot_defaults）を既定値として提示する（仕様書6.5「初期値」）。
 */
export function initSlotMinutes(
  defaults: SlotDefaultMinutesRead[],
  existing: SlotMinutesRead[] | undefined,
): SlotMinutesFormValue {
  const values: SlotMinutesFormValue = {}
  if (existing && existing.length > 0) {
    for (const row of existing) {
      if (row.slot_id !== null) {
        values[row.slot_id] = String(row.minutes)
      }
    }
    return values
  }
  for (const row of defaults) {
    values[row.slot_id] = String(row.minutes)
  }
  return values
}

/**
 * 入力欄として並べる行を組み立てる。配分済みの枠と既存実績の枠を重複なく並べ、
 * 利用者が追加した枠（addedSlotIds）も含める（仕様書6.5「未配分スロットの追加」）。
 */
export function buildSlotRows(
  defaults: SlotDefaultMinutesRead[],
  existing: SlotMinutesRead[] | undefined,
  addedSlotIds: number[],
  slotNames: Map<number, string>,
): SlotMinutesRow[] {
  const rows = new Map<number, SlotMinutesRow>()
  for (const row of defaults) {
    rows.set(row.slot_id, { slotId: row.slot_id, slotName: row.slot_name })
  }
  for (const row of existing ?? []) {
    if (row.slot_id !== null && !rows.has(row.slot_id)) {
      rows.set(row.slot_id, {
        slotId: row.slot_id,
        slotName: row.slot_name ?? slotNames.get(row.slot_id) ?? '',
      })
    }
  }
  for (const slotId of addedSlotIds) {
    if (!rows.has(slotId)) {
      rows.set(slotId, { slotId, slotName: slotNames.get(slotId) ?? '' })
    }
  }
  return [...rows.values()].sort((a, b) => a.slotId - b.slotId)
}

/** 入力値の合計（分）。教材の投下時間として表示する（R-14）。 */
export function sumSlotMinutes(values: SlotMinutesFormValue | undefined): number {
  return Object.values(values ?? {}).reduce((sum, value) => {
    const parsed = Number(value.trim())
    return sum + (Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0)
  }, 0)
}

/** 送信用ペイロード。0分・空欄の枠は送らない（サーバ側で行を作らないため）。 */
export function buildSlotMinutesPayload(
  values: SlotMinutesFormValue | undefined,
): SlotMinutesInput[] {
  return Object.entries(values ?? {})
    .map(([slotId, value]) => ({ slot_id: Number(slotId), minutes: Number(value.trim()) }))
    .filter((entry) => Number.isFinite(entry.minutes) && entry.minutes > 0)
    .map((entry) => ({ slot_id: entry.slot_id, minutes: Math.floor(entry.minutes) }))
}
