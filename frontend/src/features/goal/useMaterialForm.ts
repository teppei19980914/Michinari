/** 教材フォーム（MaterialsTab.tsx の MaterialForm）の入力値を保持するフック。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で、入力欄の`useState`
 * だけを切り出したものである。ここは値を持つことに徹し、送信内容を決める判定は
 * materialPayload.ts（純粋関数・単体テスト付き）に置く。
 *
 * 呼び出し元は編集対象の教材が切り替わらない前提（別の教材を編集するときはカードごと
 * 再マウントされる）のため、`material`の変化を追う処理は持たない。移設前と同じく初期値
 * としてのみ使う。 */
import { useState } from 'react'
import type { MaterialRead } from '../../api/goals'
import type { MaterialEnvironment, MaterialQualityMetricType } from './materialOptions'
import type { MaterialFormValues } from './materialPayload'

export interface MaterialFormState {
  values: MaterialFormValues
  setName: (value: string) => void
  setUnitLabel: (value: string) => void
  setTotalAmount: (value: string) => void
  setPlannedCycles: (value: string) => void
  toggleSubject: (subjectId: number) => void
  setStartDate: (value: string) => void
  setDueDateIsManual: (value: boolean) => void
  setDueDate: (value: string) => void
  setRequiredBlockMinutes: (value: string) => void
  setRequiredEnvironment: (value: MaterialEnvironment) => void
  setQualityMetricType: (value: MaterialQualityMetricType) => void
}

export function useMaterialForm(material?: MaterialRead): MaterialFormState {
  const [name, setName] = useState(material?.name ?? '')
  const [unitLabel, setUnitLabel] = useState(material?.unit_label ?? '')
  const [totalAmount, setTotalAmount] = useState(String(material?.total_amount ?? ''))
  const [plannedCycles, setPlannedCycles] = useState(String(material?.planned_cycles ?? 1))
  const [subjectIds, setSubjectIds] = useState<number[]>(material?.subject_ids ?? [])
  const [startDate, setStartDate] = useState(material?.start_date ?? '')
  const [dueDateIsManual, setDueDateIsManual] = useState(material?.due_date_is_manual ?? false)
  const [dueDate, setDueDate] = useState(material?.due_date ?? '')
  const [requiredBlockMinutes, setRequiredBlockMinutes] = useState(
    material?.required_block_minutes === null || material?.required_block_minutes === undefined
      ? ''
      : String(material.required_block_minutes),
  )
  const [requiredEnvironment, setRequiredEnvironment] = useState<MaterialEnvironment>(
    material?.required_environment ?? 'ANY',
  )
  const [qualityMetricType, setQualityMetricType] = useState<MaterialQualityMetricType>(
    material?.quality_metric_type ?? 'NONE',
  )

  const toggleSubject = (subjectId: number) => {
    setSubjectIds((current) =>
      current.includes(subjectId)
        ? current.filter((id) => id !== subjectId)
        : [...current, subjectId],
    )
  }

  return {
    values: {
      name,
      unitLabel,
      totalAmount,
      plannedCycles,
      subjectIds,
      startDate,
      dueDateIsManual,
      dueDate,
      requiredBlockMinutes,
      requiredEnvironment,
      qualityMetricType,
    },
    setName,
    setUnitLabel,
    setTotalAmount,
    setPlannedCycles,
    toggleSubject,
    setStartDate,
    setDueDateIsManual,
    setDueDate,
    setRequiredBlockMinutes,
    setRequiredEnvironment,
    setQualityMetricType,
  }
}
