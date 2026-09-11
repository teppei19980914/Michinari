import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'
import type { GoalCategory } from '../../api/goals'
import { ERROR_CODES } from '../../constants/errorCodes'
import { ToastProvider } from '../../components/Toast'
import { t } from '../../locales/t'
import { CloseGoalModal } from './CloseGoalModal'

// closeGoal だけを差し替える（実通信はしない）。判定そのものは closeGoalConfirm.test.ts が
// 担うため、ここでは「押したときに何が送信され、応答で表示がどう変わるか」を検証する。
const closeGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ closeGoal }))

function renderModal(category: GoalCategory, onClosed = vi.fn()) {
  // retry を切らないと失敗時に再試行が走り、エラー経路の検証が不安定になる。
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  )
  const onClose = vi.fn()
  render(
    <CloseGoalModal goalId={1} category={category} open onClose={onClose} onClosed={onClosed} />,
    { wrapper },
  )
  return { onClose, onClosed }
}

const confirmButton = () => screen.getByRole('button', { name: t('common.action.confirm') })
const cancelButton = () => screen.getByRole('button', { name: t('common.action.cancel') })

beforeEach(() => {
  closeGoal.mockReset()
  closeGoal.mockResolvedValue({ id: 1, status: 'CLOSED_WITHOUT_RESULT' })
})

afterEach(() => {
  cleanup()
})

describe('CloseGoalModal / 読書目標', () => {
  it('shows the interruption wording instead of the exam wording', () => {
    // 報告された不具合そのもの。科目が存在しない読書目標に「受験結果が未登録の科目が
    // あります」を出してはならない。
    renderModal('READING')

    expect(screen.getByText(t('goals.detail.closeConfirm.readingBody'))).toBeTruthy()
    expect(screen.queryByText(t('goals.detail.closeConfirm.withoutResultBody'))).toBeNull()
  })

  it('closes in a single confirmation', async () => {
    const { onClosed } = renderModal('READING')

    await userEvent.click(confirmButton())

    await waitFor(() => expect(onClosed).toHaveBeenCalledTimes(1))
    expect(closeGoal).toHaveBeenCalledTimes(1)
    expect(closeGoal).toHaveBeenCalledWith(1, { confirm_without_result: true, with_result: false })
  })
})

describe('CloseGoalModal / 資格試験目標', () => {
  it('asks again with the without-result wording when the server requires confirmation', async () => {
    closeGoal.mockRejectedValueOnce(
      new ApiError(ERROR_CODES.CLOSE_CONFIRMATION_REQUIRED, '確認が必要'),
    )
    const { onClosed } = renderModal('EXAM')

    expect(screen.getByText(t('goals.detail.closeConfirm.body'))).toBeTruthy()
    await userEvent.click(confirmButton())

    await waitFor(() =>
      expect(screen.getByText(t('goals.detail.closeConfirm.withoutResultBody'))).toBeTruthy(),
    )
    expect(onClosed).not.toHaveBeenCalled()

    await userEvent.click(confirmButton())
    await waitFor(() => expect(onClosed).toHaveBeenCalledTimes(1))
    expect(closeGoal).toHaveBeenLastCalledWith(1, {
      confirm_without_result: true,
      with_result: false,
    })
  })

  it('does NOT turn a real state error into a confirmation step', async () => {
    // 2026-09-11の不具合の再発検知。クローズ済み目標への再クローズ等を「確認が必要」と
    // 誤解すると、無関係な確認文言を出したまま本当のエラーを握り潰す。
    closeGoal.mockRejectedValue(
      new ApiError(ERROR_CODES.INVALID_STATE_TRANSITION, '進行中の目標のみクローズできます'),
    )
    renderModal('EXAM')

    await userEvent.click(confirmButton())

    await waitFor(() => expect(closeGoal).toHaveBeenCalledTimes(1))
    expect(screen.queryByText(t('goals.detail.closeConfirm.withoutResultBody'))).toBeNull()
    expect(screen.getByText(t('goals.detail.closeConfirm.body'))).toBeTruthy()
    // 本当のエラーは Toast で利用者に見せる。
    expect(screen.getByText(t(`errors.${ERROR_CODES.INVALID_STATE_TRANSITION}`))).toBeTruthy()
  })

  it('forgets the confirmation state when cancelled', async () => {
    // キャンセルで確認状態が残ると、次に開いたとき「確定」1回で結果なしクローズが
    // 確定してしまう。
    closeGoal.mockRejectedValueOnce(
      new ApiError(ERROR_CODES.CLOSE_CONFIRMATION_REQUIRED, '確認が必要'),
    )
    const { onClose } = renderModal('EXAM')

    await userEvent.click(confirmButton())
    await waitFor(() =>
      expect(screen.getByText(t('goals.detail.closeConfirm.withoutResultBody'))).toBeTruthy(),
    )

    await userEvent.click(cancelButton())

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.getByText(t('goals.detail.closeConfirm.body'))).toBeTruthy()
  })
})

describe('CloseGoalModal / 仕事目標', () => {
  it('offers an explicit with/without result choice', async () => {
    const { onClosed } = renderModal('WORK')

    expect(screen.getByText(t('goals.detail.closeConfirm.workBody'))).toBeTruthy()
    expect(screen.queryByRole('button', { name: t('common.action.confirm') })).toBeNull()

    await userEvent.click(
      screen.getByRole('button', { name: t('goals.detail.closeConfirm.workWithResult') }),
    )

    await waitFor(() => expect(onClosed).toHaveBeenCalledTimes(1))
    expect(closeGoal).toHaveBeenCalledWith(1, { confirm_without_result: false, with_result: true })
  })

  it('sends without_result for the cancellation path', async () => {
    renderModal('WORK')

    await userEvent.click(
      screen.getByRole('button', { name: t('goals.detail.closeConfirm.workWithoutResult') }),
    )

    await waitFor(() => expect(closeGoal).toHaveBeenCalledTimes(1))
    expect(closeGoal).toHaveBeenCalledWith(1, { confirm_without_result: false, with_result: false })
  })
})

describe('CloseGoalModal / 共通', () => {
  it('renders nothing while closed', () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <CloseGoalModal
            goalId={1}
            category="READING"
            open={false}
            onClose={vi.fn()}
            onClosed={vi.fn()}
          />
        </ToastProvider>
      </QueryClientProvider>,
    )

    expect(screen.queryByText(t('goals.detail.closeConfirm.readingBody'))).toBeNull()
  })
})
