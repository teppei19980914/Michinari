import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { Tooltip } from '../../components/Tooltip'
import { useToast } from '../../components/Toast'
import { apiClient } from '../../api/client'
import {
  createMaterial,
  deactivateMaterial,
  deleteMaterial,
  updateMaterial,
  type GoalDetailRead,
  type MaterialRead,
} from '../../api/goals'
import { computeAutoDueDate } from './materialDueDate'
import type { components } from '../../types/api.d.ts'

type SlotCheckRead = components['schemas']['SlotCheckRead']
const ENVIRONMENTS = ['ANY', 'PC', 'MOBILE'] as const
const QUALITY_METRIC_TYPES = ['NONE', 'OBJECTIVE', 'SELF_SCORED', 'SUBJECTIVE'] as const

function SlotCheckWarning({ materialId }: { materialId: number }) {
  const query = useQuery({
    queryKey: ['material-slot-check', materialId],
    queryFn: () => apiClient.get<SlotCheckRead>(`/materials/${materialId}/slot-check`),
  })
  if (!query.data || query.data.sufficient) {
    return null
  }
  return (
    <p className="mt-1 text-xs text-amber-700">{t('goals.materials.slotInsufficientWarning')}</p>
  )
}

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
  const [requiredEnvironment, setRequiredEnvironment] = useState<(typeof ENVIRONMENTS)[number]>(
    material?.required_environment ?? 'ANY',
  )
  const [qualityMetricType, setQualityMetricType] = useState<
    (typeof QUALITY_METRIC_TYPES)[number]
  >(material?.quality_metric_type ?? 'NONE')

  const toggleSubject = (subjectId: number) => {
    setSubjectIds((current) =>
      current.includes(subjectId)
        ? current.filter((id) => id !== subjectId)
        : [...current, subjectId],
    )
  }

  const autoDueDate = computeAutoDueDate(goal.exam_subjects, subjectIds)
  const effectiveDueDate = dueDateIsManual ? dueDate || null : autoDueDate
  const startDateError =
    startDate && effectiveDueDate && startDate > effectiveDueDate
      ? t('goals.materials.startDateAfterDueDateError', { dueDate: effectiveDueDate })
      : null

  const mutation = useMutation({
    mutationFn: () => {
      const shared = {
        name,
        unit_label: unitLabel,
        total_amount: Number(totalAmount),
        planned_cycles: Number(plannedCycles),
        subject_ids: subjectIds,
        start_date: startDate,
        due_date_is_manual: dueDateIsManual,
        due_date: dueDateIsManual ? dueDate || null : null,
        required_block_minutes: requiredBlockMinutes === '' ? null : Number(requiredBlockMinutes),
        required_environment: requiredEnvironment,
        quality_metric_type: qualityMetricType,
      }
      return material ? updateMaterial(material.id, shared) : createMaterial(goal.id, shared)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })
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
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.unitLabel')}
          <Input value={unitLabel} onChange={(e) => setUnitLabel(e.target.value)} required />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.totalAmountLabel')}
          <Input
            type="number"
            min={0}
            value={totalAmount}
            onChange={(e) => setTotalAmount(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.plannedCyclesLabel')}
          <Input
            type="number"
            min={1}
            value={plannedCycles}
            onChange={(e) => setPlannedCycles(e.target.value)}
            required
          />
        </label>
      </div>
      <fieldset className="flex flex-col gap-1 text-sm text-gray-700">
        <legend>{t('goals.materials.subjectsLabel')}</legend>
        <div className="flex flex-wrap gap-3">
          {goal.exam_subjects.map((subject) => (
            <label key={subject.id} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={subjectIds.includes(subject.id)}
                onChange={() => toggleSubject(subject.id)}
              />
              {subject.name}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.startDateLabel')}
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          <span className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={dueDateIsManual}
              onChange={(e) => setDueDateIsManual(e.target.checked)}
            />
            {t('goals.materials.dueDateManualLabel')}
          </span>
          <Input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            disabled={!dueDateIsManual}
          />
          {!dueDateIsManual && autoDueDate && (
            <p className="text-xs text-gray-500">
              {t('goals.materials.autoDueDatePreview', { dueDate: autoDueDate })}
            </p>
          )}
        </label>
      </div>
      {startDateError && <p className="text-xs text-red-700">{startDateError}</p>}
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.requiredBlockMinutesLabel')}
          <Input
            type="number"
            min={1}
            value={requiredBlockMinutes}
            onChange={(e) => setRequiredBlockMinutes(e.target.value)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.requiredEnvironmentLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={requiredEnvironment}
            onChange={(e) =>
              setRequiredEnvironment(e.target.value as (typeof ENVIRONMENTS)[number])
            }
          >
            {ENVIRONMENTS.map((value) => (
              <option key={value} value={value}>
                {t(`goals.materials.environment.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          <Tooltip label={t('goals.materials.qualityMetricTypeTooltip')}>
            <span>{t('goals.materials.qualityMetricTypeLabel')}</span>
          </Tooltip>
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={qualityMetricType}
            onChange={(e) =>
              setQualityMetricType(e.target.value as (typeof QUALITY_METRIC_TYPES)[number])
            }
          >
            {QUALITY_METRIC_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`goals.materials.qualityMetricType.${value}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button
          type="submit"
          disabled={mutation.isPending || subjectIds.length === 0 || !!startDateError}
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

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })

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
          <Card key={material.id}>
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-gray-900">{material.name}</p>
                <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600 sm:grid-cols-4">
                  <div>
                    <dt className="text-gray-400">{t('goals.materials.totalWork')}</dt>
                    <dd>
                      {material.total_work}
                      {material.unit_label}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">{t('goals.materials.currentCycle')}</dt>
                    <dd>
                      {t('goals.materials.cycleLabel', {
                        current: material.current_cycle,
                        planned: material.planned_cycles,
                      })}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">{t('goals.materials.cycleProgress')}</dt>
                    <dd>{Math.round(material.progress_rate_in_cycle * 100)}%</dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">{t('goals.materials.overallProgress')}</dt>
                    <dd>{Math.round(material.progress_rate * 100)}%</dd>
                  </div>
                </dl>
                <SlotCheckWarning materialId={material.id} />
              </div>
              {!readOnly && (
                <div className="flex flex-col gap-2">
                  <Button variant="secondary" onClick={() => setEditingId(material.id)}>
                    {t('common.action.edit')}
                  </Button>
                  {material.is_active && (
                    <Button
                      variant="secondary"
                      onClick={() => deactivateMutation.mutate(material.id)}
                    >
                      {t('goals.materials.deactivate')}
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    onClick={() => {
                      if (window.confirm(t('common.confirmDelete'))) {
                        deleteMutation.mutate(material.id)
                      }
                    }}
                  >
                    {t('common.action.delete')}
                  </Button>
                </div>
              )}
            </div>
          </Card>
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
