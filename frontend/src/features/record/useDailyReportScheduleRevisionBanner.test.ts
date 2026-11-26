/** `use*.ts`はカバレッジ閾値の対象外（vite.config.ts）だが、非自明な状態遷移
 * （生成中→成功/対象なし/失敗）を持つため直接テストする（useScheduleEditorState.test.tsx
 * と同じ方針、OPERATIONS.md「フロントエンドのテストとカバレッジ」）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useDailyReportScheduleRevisionBanner } from './useDailyReportScheduleRevisionBanner'

const generateScheduleRevisionProposal = vi.hoisted(() => vi.fn())
vi.mock('../../api/schedule', () => ({ generateScheduleRevisionProposal }))

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useDailyReportScheduleRevisionBanner', () => {
  it('marks a goal as generating immediately, then succeeded once a proposal is created', async () => {
    generateScheduleRevisionProposal.mockResolvedValue({ proposal: { id: 1 } })
    const { result } = renderHook(() => useDailyReportScheduleRevisionBanner())

    act(() => {
      result.current.generateForGoals([10], '2026-11-25')
    })

    expect(result.current.statusByGoalId[10]).toBe('generating')
    await waitFor(() => expect(result.current.statusByGoalId[10]).toBe('succeeded'))
    expect(generateScheduleRevisionProposal).toHaveBeenCalledWith(10, {
      trigger: 'AUTO',
      record_date: '2026-11-25',
    })
  })

  it('marks a goal as no_proposal when nothing needed to change', async () => {
    generateScheduleRevisionProposal.mockResolvedValue({ proposal: null })
    const { result } = renderHook(() => useDailyReportScheduleRevisionBanner())

    act(() => {
      result.current.generateForGoals([10], '2026-11-25')
    })

    await waitFor(() => expect(result.current.statusByGoalId[10]).toBe('no_proposal'))
  })

  it('marks a goal as failed when the generation call rejects', async () => {
    generateScheduleRevisionProposal.mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useDailyReportScheduleRevisionBanner())

    act(() => {
      result.current.generateForGoals([10], '2026-11-25')
    })

    await waitFor(() => expect(result.current.statusByGoalId[10]).toBe('failed'))
  })

  it('tracks multiple goals independently', async () => {
    generateScheduleRevisionProposal.mockImplementation((goalId: number) =>
      Promise.resolve({ proposal: goalId === 10 ? { id: 1 } : null }),
    )
    const { result } = renderHook(() => useDailyReportScheduleRevisionBanner())

    act(() => {
      result.current.generateForGoals([10, 20], '2026-11-25')
    })

    await waitFor(() => expect(result.current.statusByGoalId[10]).toBe('succeeded'))
    await waitFor(() => expect(result.current.statusByGoalId[20]).toBe('no_proposal'))
  })
})
