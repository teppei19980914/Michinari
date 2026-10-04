/** 完了・中断の確認（開発Todo 1-3）。確認は1回で、種別ごとの文言で別のAPIを呼ぶことを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ApiError } from '../../api/client'
import { GoalEndModal } from './GoalEndModal'

const completeGoal = vi.hoisted(() => vi.fn())
const abandonGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ completeGoal, abandonGoal }))

beforeEach(() => {
  vi.clearAllMocks()
  completeGoal.mockResolvedValue({})
  abandonGoal.mockResolvedValue({})
})

afterEach(() => {
  cleanup()
})

describe('GoalEndModal', () => {
  it('shows the reading wording for completing a reading goal', () => {
    renderWithProviders(
      <GoalEndModal goalId={3} category="READING" kind="complete" open onClose={() => {}} onDone={() => {}} />,
    )

    expect(screen.getByText(t('goals.end.complete.READING.title'))).toBeTruthy()
    expect(screen.getByText(t('goals.end.complete.READING.body'))).toBeTruthy()
  })

  it('completes the goal once the user confirms, and reports done', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    renderWithProviders(
      <GoalEndModal goalId={3} category="EXAM" kind="complete" open onClose={() => {}} onDone={onDone} />,
    )

    await user.click(screen.getByRole('button', { name: t('goals.end.complete.confirmButton') }))

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
    expect(completeGoal).toHaveBeenCalledWith(3)
    expect(abandonGoal).not.toHaveBeenCalled()
  })

  it('abandons the goal for an abandon request, not completes it', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    renderWithProviders(
      <GoalEndModal goalId={5} category="WORK" kind="abandon" open onClose={() => {}} onDone={onDone} />,
    )

    await user.click(screen.getByRole('button', { name: t('goals.end.abandon.confirmButton') }))

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
    expect(abandonGoal).toHaveBeenCalledWith(5)
    expect(completeGoal).not.toHaveBeenCalled()
  })

  it('does nothing when the user cancels', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderWithProviders(
      <GoalEndModal goalId={3} category="EXAM" kind="complete" open onClose={onClose} onDone={() => {}} />,
    )

    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(onClose).toHaveBeenCalled()
    expect(completeGoal).not.toHaveBeenCalled()
  })

  it('keeps the modal open and shows the error when the server refuses', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    completeGoal.mockRejectedValue(new ApiError('EXAM_RESULTS_INCOMPLETE', '結果が揃っていません'))
    renderWithProviders(
      <GoalEndModal goalId={3} category="EXAM" kind="complete" open onClose={() => {}} onDone={onDone} />,
    )

    await user.click(screen.getByRole('button', { name: t('goals.end.complete.confirmButton') }))

    expect(await screen.findByText(t('errors.EXAM_RESULTS_INCOMPLETE'))).toBeTruthy()
    expect(onDone).not.toHaveBeenCalled()
  })
})
