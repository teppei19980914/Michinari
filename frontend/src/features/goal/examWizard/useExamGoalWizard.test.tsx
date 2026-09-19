/** useExamGoalWizard の回帰テスト。
 *
 * ExamGoalWizardPage.test.tsx はテンプレート選択からの正常系（happy path）2ルートしか
 * 検証しておらず、runStepのcatch節（APIエラー時にトースト表示・isSubmitting解除）や
 * 各ステップ関数の先頭にある`if (s.goalId === null) return`等の早期returnガードは
 * 一度も直接検証されていなかった（2026-09-19、テスト全般の抜け漏れ調査で発覚）。
 * 正常系はExamGoalWizardPage.test.tsxが担うため、本ファイルはエラー処理とガード条件に絞る
 * （CODING_RULES.md「①DRYの原則」。同じ経路を2箇所で検証しない）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { t } from '../../../locales/t'
import { ToastProvider } from '../../../components/Toast'
import { useExamGoalWizard } from './useExamGoalWizard'

const listExamTemplates = vi.hoisted(() => vi.fn())
vi.mock('../../../api/examTemplates', () => ({ listExamTemplates }))

const createGoal = vi.hoisted(() => vi.fn())
const activateGoal = vi.hoisted(() => vi.fn())
const listSlotAllocations = vi.hoisted(() => vi.fn())
const updateSlotAllocations = vi.hoisted(() => vi.fn())
vi.mock('../../../api/goals', () => ({
  createGoal,
  activateGoal,
  listSlotAllocations,
  updateSlotAllocations,
}))

const listSlots = vi.hoisted(() => vi.fn())
vi.mock('../../../api/resources', () => ({ listSlots }))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../../../api/records', () => ({ getToday }))

// replaceSubjects/replaceMaterials/createAndAllocateSimpleSlotsの内部組み立ては
// examWizardSubmit.test.tsが検証済みのため、ここではモックしてフック自身の配線
// （ガード・catch・finally）だけを切り出して検証する。
const replaceSubjects = vi.hoisted(() => vi.fn())
const replaceMaterials = vi.hoisted(() => vi.fn())
const createAndAllocateSimpleSlots = vi.hoisted(() => vi.fn())
vi.mock('./examWizardSubmit', () => ({ replaceSubjects, replaceMaterials, createAndAllocateSimpleSlots }))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }))

function renderWizardHook() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    )
  }
  return renderHook(() => useExamGoalWizard(), { wrapper: Wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
  listExamTemplates.mockResolvedValue([])
  listSlots.mockResolvedValue([])
  getToday.mockResolvedValue({ logical_date: '2026-09-20' })
})

afterEach(() => {
  cleanup()
})

describe('useExamGoalWizard（goalId未確定時の早期returnガード）', () => {
  it('does not advance or call any API when goToStep3/4/5・activate run before a goal exists', async () => {
    const { result } = renderWizardHook()

    await act(async () => {
      await result.current.goToStep3()
    })
    expect(replaceSubjects).not.toHaveBeenCalled()
    expect(result.current.step).toBe(1)
    expect(result.current.isSubmitting).toBe(false)

    await act(async () => {
      await result.current.goToStep4()
    })
    expect(replaceMaterials).not.toHaveBeenCalled()
    expect(result.current.step).toBe(1)

    await act(async () => {
      await result.current.goToStep5()
    })
    expect(updateSlotAllocations).not.toHaveBeenCalled()
    expect(createAndAllocateSimpleSlots).not.toHaveBeenCalled()
    expect(result.current.step).toBe(1)

    await act(async () => {
      await result.current.activate()
    })
    expect(activateGoal).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('does not create a goal via goToStep2 while today\'s logical date has not loaded yet', async () => {
    // todayQueryが解決する前にgoToStep2が呼ばれた場合の早期return(L127-128)。
    getToday.mockReturnValue(new Promise(() => {}))
    const { result } = renderWizardHook()

    await act(async () => {
      await result.current.goToStep2()
    })

    expect(createGoal).not.toHaveBeenCalled()
    expect(result.current.step).toBe(1)
  })
})

describe('useExamGoalWizard（runStepのエラー処理）', () => {
  it('shows an error toast and resets isSubmitting when a step action throws, without advancing the step', async () => {
    createGoal.mockResolvedValue({ id: 1 })
    const { result } = renderWizardHook()
    // goToStep2はtodayQuery.data（画面には出ないクエリ）が届くまで早期returnするため、
    // 先に初期クエリの解決を待つ（同時に走るtemplatesQueryの成功を目印にする）。
    await waitFor(() => expect(result.current.templatesQuery.isSuccess).toBe(true))

    // 先にgoalIdを確定させる(goToStep2の正常系)。
    await act(async () => {
      await result.current.goToStep2()
    })
    expect(result.current.step).toBe(2)

    replaceSubjects.mockRejectedValue(new Error('boom'))

    await act(async () => {
      await result.current.goToStep3()
    })

    // catch節でshowApiErrorが呼ばれ、既定のエラー文言のトーストが出ることを確認する
    // (Error型はApiErrorではないため apiErrorMessage は errors.default を返す)。
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
    // 例外を投げた場合はs.setStep(3)まで到達しないため、ステップは進まない。
    expect(result.current.step).toBe(2)
    // finally節でisSubmittingが解除される。
    expect(result.current.isSubmitting).toBe(false)
  })
})
