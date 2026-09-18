import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../../locales/t'
import { emptyMaterialDraft, type ExamMaterialDraft, type ExamSubjectDraft } from './examWizardDrafts'
import { Step3Materials } from './Step3Materials'

const SUBJECTS: ExamSubjectDraft[] = [
  { name: '科目A', passingScore: '60', examDateType: 'RANGE', examDateFrom: '', examDateTo: '', examDateFixed: '' },
  { name: '', passingScore: '60', examDateType: 'RANGE', examDateFrom: '', examDateTo: '', examDateFixed: '' },
]

const MATERIAL: ExamMaterialDraft = {
  name: '教科書',
  unitLabel: 'ページ',
  totalAmount: '500',
  plannedCycles: '1',
  subjectNames: ['科目A'],
}

/** Step2SubjectsAndDates.test.tsxと同じ理由（コントロールドコンポーネントは実際に
 * 再描画されないと複数キーの入力が反映されない）で、状態を持つ親を模す。 */
function Harness({
  initial,
  onChange,
}: {
  initial: ExamMaterialDraft[]
  onChange: (next: ExamMaterialDraft[]) => void
}) {
  const [materials, setMaterials] = useState(initial)
  return (
    <Step3Materials
      materials={materials}
      subjects={SUBJECTS}
      onChangeMaterials={(next) => {
        onChange(next)
        setMaterials(next)
      }}
    />
  )
}

describe('Step3Materials', () => {
  it('adds a blank material when "add" is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[]} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: t('goals.examWizard.step3.addMaterial') }))

    expect(onChange).toHaveBeenCalledWith([emptyMaterialDraft()])
  })

  it('shows a fallback label for a subject without a name yet', () => {
    render(<Harness initial={[MATERIAL]} onChange={vi.fn()} />)

    expect(screen.getByText(t('goals.examWizard.step3.unnamedSubject'))).toBeDefined()
  })

  it('updates the total amount field', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[MATERIAL]} onChange={onChange} />)

    await user.clear(screen.getByLabelText(t('goals.materials.totalAmountLabel')))
    await user.type(screen.getByLabelText(t('goals.materials.totalAmountLabel')), '300')

    expect(onChange).toHaveBeenLastCalledWith([{ ...MATERIAL, totalAmount: '300' }])
  })

  it('updates the name, unit and planned cycles fields', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[MATERIAL]} onChange={onChange} />)

    await user.type(screen.getByLabelText(t('goals.materials.nameLabel')), 'X')
    await user.type(screen.getByLabelText(t('goals.materials.unitLabel')), 'Y')
    await user.clear(screen.getByLabelText(t('goals.materials.plannedCyclesLabel')))
    await user.type(screen.getByLabelText(t('goals.materials.plannedCyclesLabel')), '3')

    expect(onChange).toHaveBeenLastCalledWith([
      {
        name: '教科書X',
        unitLabel: 'ページY',
        totalAmount: '500',
        plannedCycles: '3',
        subjectNames: ['科目A'],
      },
    ])
  })

  it('toggles a subject checkbox off and back on', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial={[MATERIAL]} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: '科目A' }))
    expect(onChange).toHaveBeenLastCalledWith([{ ...MATERIAL, subjectNames: [] }])

    await user.click(screen.getByRole('checkbox', { name: '科目A' }))
    expect(onChange).toHaveBeenLastCalledWith([MATERIAL])
  })

  it('edits only the targeted material, leaving the others untouched', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const other = { ...MATERIAL, name: '問題集' }
    render(<Harness initial={[MATERIAL, other]} onChange={onChange} />)

    await user.type(screen.getAllByLabelText(t('goals.materials.nameLabel'))[1], 'X')

    expect(onChange).toHaveBeenLastCalledWith([MATERIAL, { ...other, name: '問題集X' }])
  })

  it('removes a material when delete is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <Harness initial={[MATERIAL, { ...MATERIAL, name: '問題集' }]} onChange={onChange} />,
    )

    await user.click(screen.getAllByRole('button', { name: t('common.action.delete') })[0])

    expect(onChange).toHaveBeenCalledWith([{ ...MATERIAL, name: '問題集' }])
  })
})
