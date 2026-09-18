import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { t } from '../../../locales/t'
import { Step5Confirm } from './Step5Confirm'

describe('Step5Confirm', () => {
  it('shows the range dates for a RANGE subject', () => {
    render(
      <Step5Confirm
        examName="基本情報技術者試験"
        subjects={[
          { name: '科目A', passingScore: '60', examDateType: 'RANGE', examDateFrom: '2026-11-01', examDateTo: '2026-11-30', examDateFixed: '' },
        ]}
        materials={[]}
      />,
    )

    expect(screen.getByText('基本情報技術者試験')).toBeDefined()
    expect(screen.getByText('科目A ― 2026-11-01 〜 2026-11-30')).toBeDefined()
  })

  it('shows the fixed date for a FIXED subject', () => {
    render(
      <Step5Confirm
        examName="基本情報技術者試験"
        subjects={[
          { name: '科目A', passingScore: '60', examDateType: 'FIXED', examDateFrom: '', examDateTo: '', examDateFixed: '2026-11-15' },
        ]}
        materials={[]}
      />,
    )

    expect(screen.getByText('科目A ― 2026-11-15')).toBeDefined()
  })

  it('lists materials with their amount, unit and cycles', () => {
    render(
      <Step5Confirm
        examName="基本情報技術者試験"
        subjects={[]}
        materials={[{ name: '教科書', unitLabel: 'ページ', totalAmount: '500', plannedCycles: '2', subjectNames: [] }]}
      />,
    )

    expect(screen.getByText(`教科書（500ページ × 2${t('goals.examWizard.step5.cyclesUnit')}）`)).toBeDefined()
  })

  it('shows the advanced settings notice', () => {
    render(<Step5Confirm examName="試験" subjects={[]} materials={[]} />)

    expect(screen.getByText(t('goals.examWizard.step5.advancedSettingsNotice'))).toBeDefined()
  })
})
