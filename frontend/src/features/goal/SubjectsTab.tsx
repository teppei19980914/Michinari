import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { getToday } from '../../api/records'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { Tooltip } from '../../components/Tooltip'
import { useToast } from '../../components/Toast'
import { isSubjectRangeStartInPast } from './subjectWarnings'
import {
  buildPassingScorePayload,
  formatPassingScoreDisplay,
  initPassingScoreFormState,
  type PassingScoreType,
} from './passingScore'
import {
  createSubject,
  deleteSubject,
  fixSubjectDate,
  updateSubject,
  type GoalDetailRead,
  type SubjectRead,
} from '../../api/goals'

const EXAM_DATE_TYPES = ['RANGE', 'FIXED'] as const
const PASSING_SCORE_TYPES: PassingScoreType[] = ['PERCENTAGE', 'RAW_SCORE']

function SubjectForm({
  goalId,
  subject,
  onDone,
}: {
  goalId: number
  subject?: SubjectRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [name, setName] = useState(subject?.name ?? '')
  const [examDateType, setExamDateType] = useState<(typeof EXAM_DATE_TYPES)[number]>(
    subject?.exam_date_type ?? 'RANGE',
  )
  const [examDateFrom, setExamDateFrom] = useState(subject?.exam_date_from ?? '')
  const [examDateTo, setExamDateTo] = useState(subject?.exam_date_to ?? '')
  const [examDateFixed, setExamDateFixed] = useState(subject?.exam_date_fixed ?? '')
  const [passingScoreForm, setPassingScoreForm] = useState(() =>
    initPassingScoreFormState(subject),
  )

  const payload = {
    name,
    exam_date_type: examDateType,
    exam_date_from: examDateType === 'RANGE' ? examDateFrom || null : null,
    exam_date_to: examDateType === 'RANGE' ? examDateTo || null : null,
    exam_date_fixed: examDateType === 'FIXED' ? examDateFixed || null : null,
    ...buildPassingScorePayload(passingScoreForm),
  }

  const mutation = useMutation({
    mutationFn: () =>
      subject ? updateSubject(subject.id, payload) : createSubject(goalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
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
        {t('goals.subjects.nameLabel')}
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        <Tooltip label={t('goals.subjects.examDateTypeTooltip')}>
          <span>{t('goals.subjects.examDateTypeLabel')}</span>
        </Tooltip>
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={examDateType}
          onChange={(e) => setExamDateType(e.target.value as (typeof EXAM_DATE_TYPES)[number])}
        >
          {EXAM_DATE_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`goals.subjects.examDateType.${value}`)}
            </option>
          ))}
        </select>
      </label>
      {examDateType === 'RANGE' ? (
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.examDateFromLabel')}
            <Input
              type="date"
              value={examDateFrom}
              onChange={(e) => setExamDateFrom(e.target.value)}
              required
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.examDateToLabel')}
            <Input
              type="date"
              value={examDateTo}
              onChange={(e) => setExamDateTo(e.target.value)}
              required
            />
          </label>
        </div>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.subjects.examDateFixedLabel')}
          <Input
            type="date"
            value={examDateFixed}
            onChange={(e) => setExamDateFixed(e.target.value)}
            required
          />
        </label>
      )}
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.subjects.passingScoreTypeLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={passingScoreForm.type}
          onChange={(e) =>
            setPassingScoreForm((prev) => ({
              ...prev,
              type: e.target.value as PassingScoreType,
            }))
          }
        >
          {PASSING_SCORE_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`goals.subjects.passingScoreType.${value}`)}
            </option>
          ))}
        </select>
      </label>
      {passingScoreForm.type === 'RAW_SCORE' ? (
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.passingScoreRawLabel')}
            <Input
              type="number"
              min={0}
              value={passingScoreForm.rawScoreValue}
              onChange={(e) =>
                setPassingScoreForm((prev) => ({ ...prev, rawScoreValue: e.target.value }))
              }
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.passingScoreMaxLabel')}
            <Input
              type="number"
              min={0}
              value={passingScoreForm.rawMaxValue}
              onChange={(e) =>
                setPassingScoreForm((prev) => ({ ...prev, rawMaxValue: e.target.value }))
              }
            />
          </label>
        </div>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.subjects.passingScoreLabel')}
          <Input
            type="number"
            min={0}
            max={100}
            value={passingScoreForm.percentValue}
            onChange={(e) =>
              setPassingScoreForm((prev) => ({ ...prev, percentValue: e.target.value }))
            }
          />
        </label>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

function FixDateModal({
  goalId,
  subject,
  onClose,
}: {
  goalId: number
  subject: SubjectRead
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [examDateFixed, setExamDateFixed] = useState(subject.exam_date_from ?? '')

  const mutation = useMutation({
    mutationFn: () => fixSubjectDate(subject.id, examDateFixed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
      onClose()
    },
    onError: showApiError,
  })

  return (
    <Modal open onClose={onClose} title={t('goals.subjects.fixDateConfirm.title')}>
      <p className="mb-3 text-sm text-gray-700">{t('goals.subjects.fixDateConfirm.body')}</p>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.subjects.examDateFixedLabel')}
        <Input
          type="date"
          value={examDateFixed}
          onChange={(e) => setExamDateFixed(e.target.value)}
          required
        />
      </label>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          {t('common.action.cancel')}
        </Button>
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.confirm')}
        </Button>
      </div>
    </Modal>
  )
}

/** 試験科目タブ（仕様書6.2）。 */
export function SubjectsTab({ goal, readOnly }: { goal: GoalDetailRead; readOnly: boolean }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [fixDateSubject, setFixDateSubject] = useState<SubjectRead | null>(null)
  const todayQuery = useQuery({ queryKey: ['today'], queryFn: getToday })

  const deleteMutation = useMutation({
    mutationFn: (subjectId: number) => deleteSubject(subjectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goal', goal.id] }),
    onError: showApiError,
  })

  return (
    <div className="flex flex-col gap-3">
      {goal.exam_subjects.length === 0 && !addOpen && (
        <p className="text-sm text-gray-500">{t('goals.subjects.empty')}</p>
      )}

      {goal.exam_subjects.map((subject) =>
        editingId === subject.id ? (
          <Card key={subject.id}>
            <SubjectForm goalId={goal.id} subject={subject} onDone={() => setEditingId(null)} />
          </Card>
        ) : (
          <Card key={subject.id} className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">{subject.name}</p>
              <p className="text-sm text-gray-500">
                {t(`goals.subjects.examDateType.${subject.exam_date_type}`)}:{' '}
                {subject.exam_date_type === 'RANGE'
                  ? `${subject.exam_date_from ?? '-'} 〜 ${subject.exam_date_to ?? '-'}`
                  : (subject.exam_date_fixed ?? '-')}
              </p>
              {formatPassingScoreDisplay(subject) && (
                <p className="text-sm text-gray-500">
                  {t('goals.subjects.passingScoreResultLabel')}:{' '}
                  {formatPassingScoreDisplay(subject)}
                </p>
              )}
              {isSubjectRangeStartInPast(subject, todayQuery.data?.logical_date) && (
                <p className="text-xs text-amber-700">{t('goals.subjects.pastRangeWarning')}</p>
              )}
            </div>
            {!readOnly && (
              <div className="flex gap-2">
                {subject.exam_date_type === 'RANGE' && (
                  <Button variant="secondary" onClick={() => setFixDateSubject(subject)}>
                    {t('goals.subjects.fixDate')}
                  </Button>
                )}
                <Button variant="secondary" onClick={() => setEditingId(subject.id)}>
                  {t('common.action.edit')}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (window.confirm(t('common.confirmDelete'))) {
                      deleteMutation.mutate(subject.id)
                    }
                  }}
                >
                  {t('common.action.delete')}
                </Button>
              </div>
            )}
          </Card>
        ),
      )}

      {!readOnly &&
        (addOpen ? (
          <Card>
            <SubjectForm goalId={goal.id} onDone={() => setAddOpen(false)} />
          </Card>
        ) : (
          <Button variant="secondary" onClick={() => setAddOpen(true)}>
            {t('goals.subjects.addTitle')}
          </Button>
        ))}

      {fixDateSubject && (
        <FixDateModal
          goalId={goal.id}
          subject={fixDateSubject}
          onClose={() => setFixDateSubject(null)}
        />
      )}
    </div>
  )
}
