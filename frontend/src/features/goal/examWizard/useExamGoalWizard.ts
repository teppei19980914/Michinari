/** 資格ウィザード（ExamGoalWizardPage）の状態とAPI呼び出しをまとめるフック。
 *
 * 各ステップの重い処理（科目・教材の作り直し、スロットの新規作成・配分）は
 * examWizardSubmit.ts の純粋に近い関数へ切り出し、ここでは状態の更新と
 * エラー表示（トースト）の配線に徹する（CODING_RULES.md「保守性（複雑度）」）。
 * 状態宣言（useExamWizardState）とクエリ（useExamWizardQueries）も、1関数100行の
 * 上限（CODING_RULES.md「保守性（複雑度）」）に収めるため別関数へ切り出してある。 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ROUTES } from '../../../constants/routes'
import { QUERY_KEYS } from '../../../constants/queryKeys'
import { useToast } from '../../../components/Toast'
import { listExamTemplates, type ExamTemplateRead } from '../../../api/examTemplates'
import { activateGoal, createGoal, listSlotAllocations, updateSlotAllocations } from '../../../api/goals'
import { listSlots } from '../../../api/resources'
import { getToday } from '../../../api/records'
import {
  initSlotAllocationValues,
  buildSlotAllocationPayload,
  type SlotAllocationFormValues,
} from '../slotAllocationForm'
import {
  materialDraftFromTemplate,
  subjectDraftFromTemplate,
  type ExamMaterialDraft,
  type ExamSubjectDraft,
} from './examWizardDrafts'
import { createAndAllocateSimpleSlots, replaceMaterials, replaceSubjects } from './examWizardSubmit'

export type WizardStep = 1 | 2 | 3 | 4 | 5

async function runStep(
  setIsSubmitting: (value: boolean) => void,
  showApiError: (error: unknown) => void,
  action: () => Promise<void>,
): Promise<void> {
  setIsSubmitting(true)
  try {
    await action()
  } catch (error) {
    showApiError(error)
  } finally {
    setIsSubmitting(false)
  }
}

function useExamWizardState() {
  const [step, setStep] = useState<WizardStep>(1)
  const [selection, setSelection] = useState<string | 'OTHER' | null>(null)
  const [examName, setExamName] = useState('')
  const [subjects, setSubjects] = useState<ExamSubjectDraft[]>([])
  const [materials, setMaterials] = useState<ExamMaterialDraft[]>([])
  const [goalId, setGoalId] = useState<number | null>(null)
  const [subjectIds, setSubjectIds] = useState<number[]>([])
  const [materialIds, setMaterialIds] = useState<number[]>([])
  const [weekdayHours, setWeekdayHours] = useState('')
  const [weekendHours, setWeekendHours] = useState('')
  const [slotEdits, setSlotEdits] = useState<SlotAllocationFormValues>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  return {
    step,
    setStep,
    selection,
    setSelection,
    examName,
    setExamName,
    subjects,
    setSubjects,
    materials,
    setMaterials,
    goalId,
    setGoalId,
    subjectIds,
    setSubjectIds,
    materialIds,
    setMaterialIds,
    weekdayHours,
    setWeekdayHours,
    weekendHours,
    setWeekendHours,
    slotEdits,
    setSlotEdits,
    isSubmitting,
    setIsSubmitting,
  }
}

function useExamWizardQueries(goalId: number | null, step: WizardStep) {
  const templatesQuery = useQuery({ queryKey: QUERY_KEYS.examTemplates(), queryFn: listExamTemplates })
  const todayQuery = useQuery({ queryKey: QUERY_KEYS.today(), queryFn: getToday })
  const slotsQuery = useQuery({ queryKey: QUERY_KEYS.resourceSlots(), queryFn: listSlots })
  const hasExistingSlots = (slotsQuery.data?.length ?? 0) > 0
  const slotAllocationsQuery = useQuery({
    queryKey: QUERY_KEYS.goalSlotAllocations(goalId ?? -1),
    queryFn: () => listSlotAllocations(goalId as number),
    enabled: goalId !== null && hasExistingSlots && step === 4,
  })
  return { templatesQuery, todayQuery, hasExistingSlots, slotRows: slotAllocationsQuery.data ?? [] }
}

export function useExamGoalWizard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const s = useExamWizardState()
  const { templatesQuery, todayQuery, hasExistingSlots, slotRows } = useExamWizardQueries(s.goalId, s.step)
  const slotValues: SlotAllocationFormValues = { ...initSlotAllocationValues(slotRows), ...s.slotEdits }

  function selectTemplate(template: ExamTemplateRead) {
    s.setSelection(template.id)
    s.setExamName(template.exam_name)
    s.setSubjects(template.subjects.map(subjectDraftFromTemplate))
    s.setMaterials((template.materials ?? []).map(materialDraftFromTemplate))
  }

  function selectOther() {
    s.setSelection('OTHER')
    s.setExamName('')
    s.setSubjects([])
    s.setMaterials([])
  }

  const goToStep2 = () =>
    runStep(s.setIsSubmitting, showApiError, async () => {
      if (s.goalId === null) {
        const startDate = todayQuery.data?.logical_date
        if (!startDate) return
        const goal = await createGoal({ category: 'EXAM', name: s.examName, start_date: startDate })
        s.setGoalId(goal.id)
      }
      s.setStep(2)
    })

  const goToStep3 = () =>
    runStep(s.setIsSubmitting, showApiError, async () => {
      if (s.goalId === null) return
      const created = await replaceSubjects(s.goalId, s.subjects, s.subjectIds)
      s.setSubjectIds(created.map((subject) => subject.id))
      s.setStep(3)
    })

  const goToStep4 = () =>
    runStep(s.setIsSubmitting, showApiError, async () => {
      if (s.goalId === null) return
      const startDate = todayQuery.data?.logical_date
      if (!startDate) return
      const subjectIdByName = Object.fromEntries(s.subjects.map((subject, i) => [subject.name, s.subjectIds[i]]))
      const created = await replaceMaterials(s.goalId, s.materials, s.materialIds, subjectIdByName, startDate)
      s.setMaterialIds(created.map((material) => material.id))
      s.setStep(4)
    })

  const goToStep5 = () =>
    runStep(s.setIsSubmitting, showApiError, async () => {
      if (s.goalId === null) return
      if (hasExistingSlots) {
        await updateSlotAllocations(s.goalId, buildSlotAllocationPayload(slotRows, slotValues))
      } else {
        await createAndAllocateSimpleSlots(s.goalId, Number(s.weekdayHours) || 0, Number(s.weekendHours) || 0)
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceSlots() })
      }
      s.setStep(5)
    })

  const activate = () =>
    runStep(s.setIsSubmitting, showApiError, async () => {
      if (s.goalId === null) return
      await activateGoal(s.goalId)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() })
      navigate(ROUTES.dashboard, { state: { showFirstRecordBanner: true } })
    })

  return {
    step: s.step,
    setStep: s.setStep,
    selection: s.selection,
    examName: s.examName,
    setExamName: s.setExamName,
    subjects: s.subjects,
    setSubjects: s.setSubjects,
    materials: s.materials,
    setMaterials: s.setMaterials,
    weekdayHours: s.weekdayHours,
    setWeekdayHours: s.setWeekdayHours,
    weekendHours: s.weekendHours,
    setWeekendHours: s.setWeekendHours,
    slotRows,
    slotValues,
    setSlotMinutes: (slotId: number, minutes: string) =>
      s.setSlotEdits((current) => ({ ...current, [slotId]: minutes })),
    hasExistingSlots,
    isSubmitting: s.isSubmitting,
    templatesQuery,
    selectTemplate,
    selectOther,
    goToStep2,
    goToStep3,
    goToStep4,
    goToStep5,
    activate,
  }
}
