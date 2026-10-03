/** 教材フォームの送信内容を固定する（Phase 36）。
 *
 * 描画テスト（MaterialsTab.test.tsx）が画面操作の側から同じ規則を検証しているが、
 * ここでは入力値と送信内容の対応そのものを直接押さえる。締切と所要ブロック時間の
 * `null` 化を取り違えると、サーバへ誤った値が届く。 */
import { describe, expect, it } from 'vitest'
import { buildMaterialPayload, type MaterialFormValues } from './materialPayload'

/** 全項目が入力済みの状態。各テストは検証したい項目だけを上書きする。 */
const FILLED: MaterialFormValues = {
  name: '教材A',
  unitLabel: '問',
  totalAmount: '100',
  plannedCycles: '2',
  subjectIds: [11, 12],
  startDate: '2026-09-01',
  dueDateIsManual: true,
  dueDate: '2026-11-30',
  requiredBlockMinutes: '45',
  requiredEnvironment: 'PC',
  qualityMetricType: 'OBJECTIVE',
}

describe('buildMaterialPayload', () => {
  it('sends the entered values, converting the numeric fields', () => {
    expect(buildMaterialPayload(FILLED)).toEqual({
      name: '教材A',
      unit_label: '問',
      total_amount: 100,
      planned_cycles: 2,
      subject_ids: [11, 12],
      start_date: '2026-09-01',
      due_date_is_manual: true,
      due_date: '2026-11-30',
      required_block_minutes: 45,
      required_environment: 'PC',
      quality_metric_type: 'OBJECTIVE',
    })
  })

  it('drops the entered due date while the manual switch is off', () => {
    // 自動導出へ戻した以上、入力欄に日付が残っていても送ってはいけない。
    const payload = buildMaterialPayload({ ...FILLED, dueDateIsManual: false })
    expect(payload.due_date).toBeNull()
    expect(payload.due_date_is_manual).toBe(false)
  })

  it('sends null when the manual switch is on but no date was entered', () => {
    expect(buildMaterialPayload({ ...FILLED, dueDate: '' }).due_date).toBeNull()
  })

  it('sends null instead of zero for an empty block minutes', () => {
    expect(
      buildMaterialPayload({ ...FILLED, requiredBlockMinutes: '' }).required_block_minutes,
    ).toBeNull()
  })
})
