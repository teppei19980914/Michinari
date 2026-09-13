import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import {
  createMaterial,
  deactivateMaterial,
  deleteMaterial,
  updateMaterial,
  type GoalDetailRead,
  type MaterialRead,
} from '../../api/goals'
import { computeAutoDueDate, resolveStartDateError } from './materialDueDate'
import { MaterialCard } from './MaterialCard'
import {
  MaterialAmountFields,
  MaterialConditionFields,
  MaterialScheduleFields,
  MaterialSubjectsField,
} from './MaterialFormFields'
import { buildMaterialPayload } from './materialPayload'
import { useMaterialForm } from './useMaterialForm'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 教材の追加・編集フォーム。入力欄の並びは MaterialFormFields.tsx へ、表示カードは
 * MaterialCard.tsx へ切り出してある（CODING_RULES.md「保守性（複雑度）」）。
 *
 * 送信内容を決める判定（手動締切がoffなら入力済みの日付を送らない・任意項目の空欄は
 * `null` にする・教材の有無で作成と更新を呼び分ける）はこの関数に残す。 */
function MaterialForm({
  goal,
  material,
  onDone,
}: {
  goal: GoalDetailRead
  material?: MaterialRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const form = useMaterialForm(material)
  const { values } = form

  const autoDueDate = computeAutoDueDate(goal.exam_subjects, values.subjectIds)
  const startDateError = resolveStartDateError({
    startDate: values.startDate,
    dueDateIsManual: values.dueDateIsManual,
    dueDate: values.dueDate,
    autoDueDate,
  })

  const mutation = useMutation({
    mutationFn: () => {
      const payload = buildMaterialPayload(values)
      return material ? updateMaterial(material.id, payload) : createMaterial(goal.id, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goal.id) })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.materials.nameLabel')}
        <Input value={values.name} onChange={(e) => form.setName(e.target.value)} required />
      </label>
      <MaterialAmountFields
        unitLabel={values.unitLabel}
        onChangeUnitLabel={form.setUnitLabel}
        totalAmount={values.totalAmount}
        onChangeTotalAmount={form.setTotalAmount}
        plannedCycles={values.plannedCycles}
        onChangePlannedCycles={form.setPlannedCycles}
      />
      <MaterialSubjectsField
        subjects={goal.exam_subjects}
        selectedIds={values.subjectIds}
        onToggle={form.toggleSubject}
      />
      <MaterialScheduleFields
        startDate={values.startDate}
        onChangeStartDate={form.setStartDate}
        dueDateIsManual={values.dueDateIsManual}
        onChangeDueDateIsManual={form.setDueDateIsManual}
        dueDate={values.dueDate}
        onChangeDueDate={form.setDueDate}
        autoDueDate={autoDueDate}
      />
      {startDateError && <p className="text-xs text-red-700">{startDateError}</p>}
      <MaterialConditionFields
        requiredBlockMinutes={values.requiredBlockMinutes}
        onChangeRequiredBlockMinutes={form.setRequiredBlockMinutes}
        requiredEnvironment={values.requiredEnvironment}
        onChangeRequiredEnvironment={form.setRequiredEnvironment}
        qualityMetricType={values.qualityMetricType}
        onChangeQualityMetricType={form.setQualityMetricType}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button
          type="submit"
          disabled={mutation.isPending || values.subjectIds.length === 0 || !!startDateError}
        >
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

/** 教材タブ（仕様書6.2「総作業量・現在周回・周回進捗・全体進捗」を表示。Phase7完了条件）。 */
export function MaterialsTab({ goal, readOnly }: { goal: GoalDetailRead; readOnly: boolean }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goal.id) })

  const deleteMutation = useMutation({
    mutationFn: (materialId: number) => deleteMaterial(materialId),
    onSuccess: invalidate,
    onError: showApiError,
  })
  const deactivateMutation = useMutation({
    mutationFn: (materialId: number) => deactivateMaterial(materialId),
    onSuccess: invalidate,
    onError: showApiError,
  })

  return (
    <div className="flex flex-col gap-3">
      {goal.materials.length === 0 && !addOpen && (
        <p className="text-sm text-gray-500">{t('goals.materials.empty')}</p>
      )}

      {goal.materials.map((material) =>
        editingId === material.id ? (
          <Card key={material.id}>
            <MaterialForm goal={goal} material={material} onDone={() => setEditingId(null)} />
          </Card>
        ) : (
          <MaterialCard
            key={material.id}
            material={material}
            readOnly={readOnly}
            onEdit={() => setEditingId(material.id)}
            onDeactivate={() => deactivateMutation.mutate(material.id)}
            onDelete={() => {
              if (window.confirm(t('common.confirmDelete'))) {
                deleteMutation.mutate(material.id)
              }
            }}
          />
        ),
      )}

      {!readOnly &&
        (addOpen ? (
          <Card>
            <MaterialForm goal={goal} onDone={() => setAddOpen(false)} />
          </Card>
        ) : (
          <Button variant="secondary" onClick={() => setAddOpen(true)}>
            {t('goals.materials.addTitle')}
          </Button>
        ))}
    </div>
  )
}
