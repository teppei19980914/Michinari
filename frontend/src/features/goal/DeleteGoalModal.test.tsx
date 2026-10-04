/** 目標の削除（開発Todo 1-4）。二段階の確認（目標名の入力）と、種別ごとの警告文を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { makeGoal } from '../../test/fixtures'
import { DeleteGoalModal } from './DeleteGoalModal'

const deleteGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ deleteGoal }))

beforeEach(() => {
  vi.clearAllMocks()
  deleteGoal.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('DeleteGoalModal', () => {
  it('renders nothing when no goal is targeted', () => {
    const { container } = renderWithProviders(<DeleteGoalModal goal={null} onClose={() => {}} />)

    expect(container.textContent).toBe('')
  })

  it('asks for the goal name and keeps delete disabled until it matches', async () => {
    const user = userEvent.setup()
    const goal = makeGoal({ name: '資格A' })
    renderWithProviders(<DeleteGoalModal goal={goal} onClose={() => {}} />)
    const deleteButton = screen.getByRole('button', { name: t('goals.delete.confirmButton') })
    expect((deleteButton as HTMLButtonElement).disabled).toBe(true)

    await user.type(screen.getByRole('textbox'), '資格')
    expect((deleteButton as HTMLButtonElement).disabled).toBe(true)

    await user.type(screen.getByRole('textbox'), 'A')
    expect((deleteButton as HTMLButtonElement).disabled).toBe(false)
  })

  it('deletes the goal once the name is confirmed', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const goal = makeGoal({ id: 9, name: '資格A' })
    renderWithProviders(<DeleteGoalModal goal={goal} onClose={onClose} />)

    await user.type(screen.getByRole('textbox'), '資格A')
    await user.click(screen.getByRole('button', { name: t('goals.delete.confirmButton') }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(deleteGoal).toHaveBeenCalledWith(9)
  })

  it('warns with the wording of the goal category', () => {
    renderWithProviders(
      <DeleteGoalModal goal={makeGoal({ category: 'READING', name: '本' })} onClose={() => {}} />,
    )

    expect(screen.getByText(t('goals.delete.warning.READING'))).toBeTruthy()
  })
})
