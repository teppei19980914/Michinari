import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../../locales/t'
import { emptySubjectDraft, type ExamSubjectDraft } from './examWizardDrafts'
import { Step2SubjectsAndDates } from './Step2SubjectsAndDates'

const SUBJECT_A: ExamSubjectDraft = {
  name: '科目A',
  passingScore: '60',
  examDateType: 'RANGE',
  examDateFrom: '',
  examDateTo: '',
  examDateFixed: '',
}

/** typeで複数キーを打つテストは、値が変わるたびに再描画されないと2文字目以降が
 * 正しく反映されない（コントロールドコンポーネントの既知の制約）ため、実際の画面と
 * 同じ「状態を持つ親」を模したハーネスで包む。onChangeは検証用に呼び出し内容を記録
 * しつつ、実際にstateも更新する。 */
function Harness({
  initial,
  onChange,
}: {
  initial: ExamSubjectDraft[]
  onChange: (next: ExamSubjectDraft[]) => void
}) {
  const [subjects, setSubjects] = useState(initial)
  return (
    <Step2SubjectsAndDates
      subjects={subjects}
      onChangeSubjects={(next) => {
        onChange(next)
        setSubjects(next)
      }}
    />
  )
}

describe('Step2SubjectsAndDates', () => {
  it('adds a blank subject when "add" is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[]} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: t('goals.examWizard.step2.addSubject') }))

    expect(onChange).toHaveBeenCalledWith([emptySubjectDraft()])
  })

  it('updates the name field of the right row', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[SUBJECT_A]} onChange={onChange} />)

    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), 'X')

    expect(onChange).toHaveBeenLastCalledWith([{ ...SUBJECT_A, name: '科目AX' }])
  })

  it('updates the passing score field', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[SUBJECT_A]} onChange={onChange} />)

    await user.clear(screen.getByLabelText(t('goals.subjects.passingScoreLabel')))
    await user.type(screen.getByLabelText(t('goals.subjects.passingScoreLabel')), '70')

    expect(onChange).toHaveBeenLastCalledWith([{ ...SUBJECT_A, passingScore: '70' }])
  })

  it('switches to FIXED and fills the fixed date', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[SUBJECT_A]} onChange={onChange} />)

    await user.selectOptions(screen.getByRole('combobox'), 'FIXED')
    expect(onChange).toHaveBeenLastCalledWith([{ ...SUBJECT_A, examDateType: 'FIXED' }])

    await user.type(screen.getByLabelText(t('goals.subjects.examDateFixedLabel')), '2026-11-15')

    expect(onChange).toHaveBeenLastCalledWith([
      { ...SUBJECT_A, examDateType: 'FIXED', examDateFixed: '2026-11-15' },
    ])
  })

  it('fills the range dates', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[SUBJECT_A]} onChange={onChange} />)

    await user.type(screen.getByLabelText(t('goals.subjects.examDateFromLabel')), '2026-11-01')
    await user.type(screen.getByLabelText(t('goals.subjects.examDateToLabel')), '2026-11-30')

    expect(onChange).toHaveBeenCalledWith([{ ...SUBJECT_A, examDateFrom: '2026-11-01' }])
    expect(onChange).toHaveBeenLastCalledWith([
      { ...SUBJECT_A, examDateFrom: '2026-11-01', examDateTo: '2026-11-30' },
    ])
  })

  it('removes a row when delete is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <Harness initial={[SUBJECT_A, { ...SUBJECT_A, name: '科目B' }]} onChange={onChange} />,
    )

    await user.click(screen.getAllByRole('button', { name: t('common.action.delete') })[0])

    expect(onChange).toHaveBeenCalledWith([{ ...SUBJECT_A, name: '科目B' }])
  })
})
