import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import { renderWithProviders } from '../../test/renderWithProviders'
import { t } from '../../locales/t'
import type { GoalCategory, GoalRead } from '../../api/goals'
import { DeleteArchivedGoalModal } from './DeleteArchivedGoalModal'
import { resolveDeleteGoalLabelKeys } from './deleteGoalLabels'

const deleteArchivedGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ deleteArchivedGoal }))

function makeGoal(category: GoalCategory): GoalRead {
  return {
    id: 1,
    category,
    name: '目標A',
    start_date: '2026-01-01',
    status: 'CLOSED_WITHOUT_RESULT',
    memo: null,
    archived_at: '2026-02-01T00:00:00',
    closed_at: '2026-01-31T00:00:00',
    activated_at: '2026-01-01T00:00:00',
  } as GoalRead
}

function renderModal(goal: GoalRead | null) {
  const onClose = vi.fn()
  renderWithProviders(<DeleteArchivedGoalModal goal={goal} onClose={onClose} />)
  return { onClose }
}

beforeEach(() => {
  deleteArchivedGoal.mockReset()
  deleteArchivedGoal.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('DeleteArchivedGoalModal', () => {
  it.each(GOAL_CATEGORIES)('describes what is deleted for a %s goal', (category) => {
    // 取り消せない操作のため、種別に合った文言でなければならない。読書目標に
    // 「科目・教材もすべて削除されます」と出ていたのが2026-09-11の指摘。
    renderModal(makeGoal(category))
    const keys = resolveDeleteGoalLabelKeys(category)

    expect(screen.getByText(t(keys.warningKey))).toBeTruthy()
    expect(screen.getByText(t(keys.cascadeHintKey))).toBeTruthy()
  })

  it('does not show the exam wording for a reading goal', () => {
    renderModal(makeGoal('READING'))

    expect(screen.queryByText(t('goals.list.deleteModal.warning'))).toBeNull()
    expect(screen.getByText(t('goals.list.deleteModal.warningReading'))).toBeTruthy()
  })

  it('renders nothing when no goal is selected', () => {
    renderModal(null)

    expect(screen.queryByText(t('goals.list.deleteModal.title'))).toBeNull()
  })

  it('deletes with the cascade flag on by default', async () => {
    const { onClose } = renderModal(makeGoal('EXAM'))

    await userEvent.click(
      screen.getByRole('button', { name: t('goals.list.deleteModal.confirmButton') }),
    )

    await waitFor(() => expect(deleteArchivedGoal).toHaveBeenCalledTimes(1))
    expect(deleteArchivedGoal).toHaveBeenCalledWith(1, { cascade_study_logs: true })
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('sends cascade=false once the checkbox is cleared', async () => {
    renderModal(makeGoal('READING'))

    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: t('goals.list.deleteModal.confirmButton') }),
    )

    await waitFor(() => expect(deleteArchivedGoal).toHaveBeenCalledTimes(1))
    expect(deleteArchivedGoal).toHaveBeenCalledWith(1, { cascade_study_logs: false })
  })

  it('closes without deleting when cancelled', async () => {
    const { onClose } = renderModal(makeGoal('WORK'))

    await userEvent.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(deleteArchivedGoal).not.toHaveBeenCalled()
  })
})
