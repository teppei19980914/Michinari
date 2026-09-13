/** 目標一覧の振る舞いを固定する（Phase 35。実環境検証の「入口から各目標へ到達できること」に相当）。
 *
 * この画面は他のすべての画面への入口であり、壊れると何もできなくなる。アーカイブは
 * 一覧から目標が消える操作のため確認ダイアログを経ることを、新規作成は送信内容と遷移先を固定する。
 *
 * 状態から遷移先・アーカイブ可否を決める判定（`goalStatus.ts`）は `goalStatus.test.ts` が、
 * 完全削除の確認は `DeleteArchivedGoalModal.test.tsx` が担うため、ここでは結線を確かめる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeGoal } from '../test/fixtures'
import { GoalsListPage } from './GoalsListPage'

const listGoals = vi.hoisted(() => vi.fn())
const createGoal = vi.hoisted(() => vi.fn())
const archiveGoal = vi.hoisted(() => vi.fn())
const unarchiveGoal = vi.hoisted(() => vi.fn())
const deleteArchivedGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({
  listGoals,
  createGoal,
  archiveGoal,
  unarchiveGoal,
  deleteArchivedGoal,
}))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

const ARCHIVED_ID = GOAL_ID + 1
const archivedGoal = () =>
  makeGoal({
    id: ARCHIVED_ID,
    name: 'アーカイブ済みの目標',
    status: 'CLOSED_WITH_RESULT',
    archived_at: '2026-09-10T00:00:00',
  })

const newGoalButton = () => screen.getByRole('button', { name: t('goals.list.newGoal') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const archiveButton = () => screen.getByRole('button', { name: t('goals.list.archiveButton') })
const showArchivedToggle = () =>
  screen.getByRole('checkbox', { name: t('goals.list.showArchivedToggle') })

beforeEach(() => {
  vi.clearAllMocks()
  listGoals.mockResolvedValue([makeGoal()])
  createGoal.mockResolvedValue(makeGoal())
  archiveGoal.mockResolvedValue(undefined)
  unarchiveGoal.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('GoalsListPage の一覧', () => {
  it('shows the empty message when there is no goal at all', async () => {
    listGoals.mockResolvedValue([])
    renderWithProviders(<GoalsListPage />)

    expect(await screen.findByText(t('goals.list.empty'))).toBeDefined()
  })

  it('links an open goal to its detail screen', async () => {
    renderWithProviders(<GoalsListPage />)

    const link = (await screen.findByText('目標A')).closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe(ROUTES.goalDetail(GOAL_ID))
  })

  it('links a closed goal to the export screen instead', async () => {
    listGoals.mockResolvedValue([makeGoal({ status: 'CLOSED_WITH_RESULT' })])
    renderWithProviders(<GoalsListPage />)

    const link = (await screen.findByText('目標A')).closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe(ROUTES.goalExport(GOAL_ID))
  })

  it('offers registering the exam result only for an active exam goal', async () => {
    const { unmount } = renderWithProviders(<GoalsListPage />)
    expect(await screen.findByText(t('goals.list.resultLink'))).toBeDefined()

    unmount()
    listGoals.mockResolvedValue([makeGoal({ category: 'READING' })])
    renderWithProviders(<GoalsListPage />)

    await screen.findByText('目標A')
    expect(screen.queryByText(t('goals.list.resultLink'))).toBeNull()
  })

  it('keeps archived goals out of the main list until the toggle is switched on', async () => {
    const user = userEvent.setup()
    listGoals.mockResolvedValue([makeGoal(), archivedGoal()])
    renderWithProviders(<GoalsListPage />)

    await screen.findByText('目標A')
    expect(screen.queryByText('アーカイブ済みの目標')).toBeNull()

    await user.click(showArchivedToggle())

    expect(screen.getByText('アーカイブ済みの目標')).toBeDefined()
    expect(screen.getByText(t('goals.list.archivedSectionTitle'))).toBeDefined()
  })

  it('hides the archive toggle when nothing is archived', async () => {
    renderWithProviders(<GoalsListPage />)

    await screen.findByText('目標A')
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})

describe('GoalsListPage のアーカイブ操作', () => {
  it('does not archive when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    // アーカイブ可能なのはクローズ済みなど「進行中ではない」目標（goalStatus.ts）。
    listGoals.mockResolvedValue([makeGoal({ status: 'PAUSED' })])
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<GoalsListPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.list.archiveButton') }))

    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(archiveGoal).not.toHaveBeenCalled()
  })

  it('archives only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    listGoals.mockResolvedValue([makeGoal({ status: 'PAUSED' })])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<GoalsListPage />)

    await screen.findByText('目標A')
    await user.click(archiveButton())

    // mutationFn を直接渡しているため、TanStack Query が第2引数にコンテキストを足す。
    // 見たいのは対象の目標IDだけなので第1引数で確かめる。
    await waitFor(() => expect(archiveGoal).toHaveBeenCalledOnce())
    expect(archiveGoal.mock.calls[0][0]).toBe(GOAL_ID)
  })

  it('does not offer archiving an active goal', async () => {
    renderWithProviders(<GoalsListPage />)

    await screen.findByText('目標A')
    expect(screen.queryByRole('button', { name: t('goals.list.archiveButton') })).toBeNull()
  })

  it('restores an archived goal without asking for a confirmation', async () => {
    const user = userEvent.setup()
    listGoals.mockResolvedValue([archivedGoal()])
    renderWithProviders(<GoalsListPage />)

    await user.click(await screen.findByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: t('goals.list.restoreButton') }))

    await waitFor(() => expect(unarchiveGoal).toHaveBeenCalledOnce())
    expect(unarchiveGoal.mock.calls[0][0]).toBe(ARCHIVED_ID)
  })

  it('asks for the goal name before deleting an archived goal for good', async () => {
    const user = userEvent.setup()
    listGoals.mockResolvedValue([archivedGoal()])
    renderWithProviders(<GoalsListPage />)

    await user.click(await screen.findByRole('checkbox'))
    await user.click(
      screen.getByRole('button', { name: t('goals.list.deleteCompletelyButton') }),
    )

    // 完全削除はこの場では実行されず、名称の入力を求める確認モーダルへ渡す。
    expect(deleteArchivedGoal).not.toHaveBeenCalled()
    expect(screen.getByText(t('goals.list.deleteModal.title'))).toBeDefined()
  })
})

describe('GoalsListPage の新規作成', () => {
  it('creates the goal and moves to its detail screen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<GoalsListPage />)

    await user.click(newGoalButton())
    await user.type(screen.getByLabelText(t('goals.new.nameLabel')), '新しい目標')
    fireEvent.change(screen.getByLabelText(t('goals.new.startDateLabel')), {
      target: { value: '2026-09-20' },
    })
    await user.click(saveButton())

    await waitFor(() => expect(createGoal).toHaveBeenCalledOnce())
    expect(createGoal).toHaveBeenCalledWith({
      category: 'EXAM',
      name: '新しい目標',
      start_date: '2026-09-20',
    })
    expect(navigate).toHaveBeenCalledWith(ROUTES.goalDetail(GOAL_ID))
  })

  it('switches the name label and the sent category together', async () => {
    const user = userEvent.setup()
    renderWithProviders(<GoalsListPage />)

    await user.click(newGoalButton())
    await user.selectOptions(screen.getByLabelText(t('goals.new.categoryLabel')), 'READING')

    // 種別を変えると入力を促す文言も切り替わる（資格試験は試験名、読書は書名）。
    expect(screen.getByLabelText(t('goals.new.nameLabelReading'))).toBeDefined()

    await user.type(screen.getByLabelText(t('goals.new.nameLabelReading')), '読みたい本')
    fireEvent.change(screen.getByLabelText(t('goals.new.startDateLabel')), {
      target: { value: '2026-09-20' },
    })
    await user.click(saveButton())

    await waitFor(() => expect(createGoal).toHaveBeenCalledOnce())
    expect(createGoal.mock.calls[0][0]).toMatchObject({ category: 'READING' })
  })

  it('closes the dialog without creating anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<GoalsListPage />)

    await user.click(newGoalButton())
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createGoal).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })
})
