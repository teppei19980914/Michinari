/** 日次報告画面のチームメンバーセクションが案件ごとに一覧を表示することを固定する
 * （要件定義書6.11「同期」）。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { makeGoal, makeWorkAssignment, makeWorkMember } from '../../test/fixtures'
import { WorkMemberSection } from './WorkMemberSection'

vi.mock('../../api/goals', () => ({}))

afterEach(() => {
  cleanup()
})

describe('WorkMemberSection', () => {
  it('renders one member block per active work assignment', () => {
    const goalA = makeGoal({ id: 1, name: '案件A' })
    const goalB = makeGoal({ id: 2, name: '案件B' })
    renderWithProviders(
      <WorkMemberSection
        workAssignments={[
          {
            goal: goalA,
            workAssignment: makeWorkAssignment({ id: 10, members: [makeWorkMember({ name: 'Aさん' })] }),
          },
          {
            goal: goalB,
            workAssignment: makeWorkAssignment({ id: 20, members: [] }),
          },
        ]}
      />,
    )

    expect(screen.getByText(t('dailyReport.workMember.title', { workName: '案件A' }))).toBeDefined()
    expect(screen.getByText(t('dailyReport.workMember.title', { workName: '案件B' }))).toBeDefined()
    expect(screen.getByText('Aさん')).toBeDefined()
  })
})
