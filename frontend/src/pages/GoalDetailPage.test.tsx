/** 目標詳細の、種別ごとのタブ構成と状態遷移の操作を固定する（Phase 35）。
 *
 * タブ構成を取り違えると、読書目標に試験科目タブが出るなど種別に存在しない設定を促してしまう。
 * 状態遷移（開始・中断・再開・クローズ）はこの画面にしか入口がなく、出し分けを誤ると
 * 目標を進められなくなる。再開時のリソース超過だけは一般的なエラー表示ではなく専用の説明を
 * 出す必要があり（原因が配分にあると分からないと利用者が対処できない）、ここを特に固定する。
 *
 * 各タブの中身はタブごとのテストが担うため、ここでは正しいタブが並ぶことと切り替わることを見る。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ApiError } from '../api/client'
import { ERROR_CODES } from '../constants/errorCodes'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail } from '../test/fixtures'
import { GoalDetailPage } from './GoalDetailPage'

const getGoal = vi.hoisted(() => vi.fn())
const activateGoal = vi.hoisted(() => vi.fn())
const pauseGoal = vi.hoisted(() => vi.fn())
const resumeGoal = vi.hoisted(() => vi.fn())
// 子タブが同じモジュールから取り込むため、描画されうる関数はすべて用意しておく。
vi.mock('../api/goals', () => ({
  getGoal,
  activateGoal,
  pauseGoal,
  resumeGoal,
  updateGoal: vi.fn(),
  createSubject: vi.fn(),
  updateSubject: vi.fn(),
  deleteSubject: vi.fn(),
  fixSubjectDate: vi.fn(),
  createMaterial: vi.fn(),
  updateMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
  deactivateMaterial: vi.fn(),
  createBook: vi.fn(),
  updateBook: vi.fn(),
  completeBook: vi.fn(),
  createWorkAssignment: vi.fn(),
  updateWorkAssignment: vi.fn(),
  createLoadProfile: vi.fn(),
  updateLoadProfile: vi.fn(),
  deleteLoadProfile: vi.fn(),
  listSlotAllocations: vi.fn(() => Promise.resolve([])),
  updateSlotAllocations: vi.fn(),
  closeGoal: vi.fn(),
}))

vi.mock('../api/records', () => ({ getToday: vi.fn(() => Promise.resolve(null)) }))

// URL から目標IDを読むため、ルートパラメータを固定する。
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useParams: () => ({ goalId: String(GOAL_ID) }),
}))

const tabButton = (labelKey: string) => screen.queryByRole('button', { name: t(labelKey) })

beforeEach(() => {
  vi.clearAllMocks()
  getGoal.mockResolvedValue(makeGoalDetail())
  activateGoal.mockResolvedValue(undefined)
  pauseGoal.mockResolvedValue(undefined)
  resumeGoal.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('GoalDetailPage の読み込みとエラー', () => {
  it('shows the loading text until the goal arrives', () => {
    getGoal.mockReturnValue(new Promise(() => undefined))
    renderWithProviders(<GoalDetailPage />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the localized message when the goal cannot be read', async () => {
    getGoal.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<GoalDetailPage />)

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).toBeDefined()
  })
})

describe('GoalDetailPage の種別ごとのタブ構成', () => {
  it('shows the exam tabs for an exam goal', async () => {
    renderWithProviders(<GoalDetailPage />)

    await screen.findByText('目標A')
    expect(tabButton('goals.detail.tabs.subjects')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.materials')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.loadProfile')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.book')).toBeNull()
    expect(tabButton('goals.detail.tabs.workAssignment')).toBeNull()
  })

  it('shows the reading tabs for a reading goal', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ category: 'READING' }))
    renderWithProviders(<GoalDetailPage />)

    await screen.findByText('目標A')
    expect(tabButton('goals.detail.tabs.book')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.resourceAllocation')).not.toBeNull()
    // 読書は定量的な進捗管理を行わないため、試験科目・教材・負荷プロファイルは出さない。
    expect(tabButton('goals.detail.tabs.subjects')).toBeNull()
    expect(tabButton('goals.detail.tabs.materials')).toBeNull()
    expect(tabButton('goals.detail.tabs.loadProfile')).toBeNull()
  })

  it('shows the work tabs for a work goal', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ category: 'WORK' }))
    renderWithProviders(<GoalDetailPage />)

    await screen.findByText('目標A')
    expect(tabButton('goals.detail.tabs.workAssignment')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.monthlyReport')).not.toBeNull()
    expect(tabButton('goals.detail.tabs.semiannualReview')).not.toBeNull()
    // 仕事はスロットを奪い合わないため配分タブを持たない。
    expect(tabButton('goals.detail.tabs.resourceAllocation')).toBeNull()
  })

  it('switches the shown tab when another one is picked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<GoalDetailPage />)

    await screen.findByText('目標A')
    await user.click(tabButton('goals.detail.tabs.subjects')!)

    expect(
      await screen.findByRole('button', { name: t('goals.subjects.addTitle') }),
    ).toBeDefined()
  })
})

describe('GoalDetailPage の状態遷移', () => {
  it('offers starting a draft goal', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'DRAFT' }))
    renderWithProviders(<GoalDetailPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.detail.action.activate') }))

    await waitFor(() => expect(activateGoal).toHaveBeenCalledWith(GOAL_ID))
  })

  it('offers pausing and closing an active goal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<GoalDetailPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.detail.action.pause') }))

    await waitFor(() => expect(pauseGoal).toHaveBeenCalledWith(GOAL_ID))
    expect(screen.getByRole('button', { name: t('goals.detail.action.close') })).toBeDefined()
  })

  it('offers resuming a paused goal', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'PAUSED' }))
    renderWithProviders(<GoalDetailPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.detail.action.resume') }))

    await waitFor(() => expect(resumeGoal).toHaveBeenCalledWith(GOAL_ID))
  })

  it('explains that the allocation is the reason when resuming is refused', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'PAUSED' }))
    resumeGoal.mockRejectedValue(new ApiError(ERROR_CODES.RESOURCE_EXCEEDED, 'サーバ側の文言'))
    renderWithProviders(<GoalDetailPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.detail.action.resume') }))

    // 一般的なエラー表示ではなく、配分を見直すよう促す専用の説明を出す。
    expect(await screen.findByText(t('goals.detail.resumeError'))).toBeDefined()
  })

  it('falls back to the generic error for any other refusal', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'PAUSED' }))
    resumeGoal.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<GoalDetailPage />)

    await user.click(await screen.findByRole('button', { name: t('goals.detail.action.resume') }))

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).toBeDefined()
    expect(screen.queryByText(t('goals.detail.resumeError'))).toBeNull()
  })

  it('hides every status action for a closed goal and says it is read only', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'CLOSED_WITH_RESULT' }))
    renderWithProviders(<GoalDetailPage />)

    expect(await screen.findByText(t('goals.detail.readOnlyNotice'))).toBeDefined()
    expect(screen.queryByRole('button', { name: t('goals.detail.action.pause') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.detail.action.activate') })).toBeNull()
  })

  it('says the goal is archived instead of read only', async () => {
    getGoal.mockResolvedValue(
      makeGoalDetail({ status: 'CLOSED_WITH_RESULT', archived_at: '2026-09-10T00:00:00' }),
    )
    renderWithProviders(<GoalDetailPage />)

    expect(await screen.findByText(t('goals.detail.archivedNotice'))).toBeDefined()
    expect(screen.queryByText(t('goals.detail.readOnlyNotice'))).toBeNull()
  })
})
