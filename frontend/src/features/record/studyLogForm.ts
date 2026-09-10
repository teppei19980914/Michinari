import { subjectiveScaleFromNormalized } from './qualityInput'
import {
  buildSlotMinutesPayload,
  initSlotMinutes,
  type SlotMinutesFormValue,
} from './slotMinutesForm'
import type { QuotaItemRead, StudyLogInput } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type StudyLogRead = components['schemas']['StudyLogRead']

/** 実績入力欄の1教材分の入力状態（文字列で保持し、送信直前に数値へ変換する）。
 *
 * 投下時間は単一の欄ではなく時間枠ごとの入力（slotMinutes）として保持し、教材の投下時間は
 * その合計とする（仕様書6.5、要件定義書R-14）。 */
export type StudyLogFormValue = {
  slotMinutes: SlotMinutesFormValue
  amountCompleted: string
  cycleNumber: string
  qualityValue: string
}

const EMPTY_VALUE: StudyLogFormValue = {
  slotMinutes: {},
  amountCompleted: '',
  cycleNumber: '',
  qualityValue: '',
}

/**
 * 実績入力欄の初期値を組み立てる（仕様書6.5「周回の既定値は算出値（現在周回）」）。
 * 既存の学習実績（進捗のみ登録済からの継続・昇格）があれば、その値で上書きする。
 * 主観的手応えはDBには正規化値（20〜100）で保存されているため、選択欄用に1〜5へ逆変換する
 * （qualityInput.subjectiveScaleFromNormalized）。
 */
export function initStudyLogFormValues(
  quotaItems: QuotaItemRead[],
  existingLogs: StudyLogRead[],
): Record<number, StudyLogFormValue> {
  const existingByMaterial = new Map(existingLogs.map((log) => [log.material_id, log]))
  const result: Record<number, StudyLogFormValue> = {}

  for (const item of quotaItems) {
    const existing = existingByMaterial.get(item.material_id)
    if (!existing) {
      result[item.material_id] = {
        ...EMPTY_VALUE,
        slotMinutes: initSlotMinutes(item.slot_defaults, undefined),
        cycleNumber: String(item.current_cycle),
      }
      continue
    }
    const quality =
      existing.quality_value === null
        ? ''
        : item.quality_metric_type === 'SUBJECTIVE'
          ? String(subjectiveScaleFromNormalized(existing.quality_value) ?? '')
          : String(existing.quality_value)
    result[item.material_id] = {
      slotMinutes: initSlotMinutes(item.slot_defaults, existing.slot_minutes),
      amountCompleted: String(existing.amount_completed),
      cycleNumber: String(existing.cycle_number),
      qualityValue: quality,
    }
  }
  return result
}

/** 入力欄に何かしら値が入っているか（一度も触れていない教材のみ確定不可、等の判定に使う）。 */
export function hasAnyStudyLogInput(values: Record<number, StudyLogFormValue>): boolean {
  return Object.values(values).some((v) => v.amountCompleted.trim() !== '')
}

/**
 * 送信用ペイロードを組み立てる。「完了分量」が未入力の教材（今日その教材に触れていない）は
 * 送信対象から除外する（StudyLogInput.amount_completedは必須のため、未入力=0とみなさない）。
 */
export function buildStudyLogPayload(
  values: Record<number, StudyLogFormValue>,
): StudyLogInput[] {
  return Object.entries(values)
    .filter(([, value]) => value.amountCompleted.trim() !== '')
    .map(([materialId, value]) => ({
      material_id: Number(materialId),
      slot_minutes: buildSlotMinutesPayload(value.slotMinutes),
      amount_completed: Number(value.amountCompleted),
      cycle_number: value.cycleNumber.trim() === '' ? null : Number(value.cycleNumber),
      quality_value: value.qualityValue.trim() === '' ? null : Number(value.qualityValue),
    }))
}
