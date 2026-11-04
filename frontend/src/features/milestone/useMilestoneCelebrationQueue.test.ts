import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useMilestoneCelebrationQueue } from './useMilestoneCelebrationQueue'
import * as milestonesApi from '../../api/milestones'
import type { MilestoneAchievement } from '../../api/milestones'

vi.mock('../../api/milestones')

function makeAchievement(overrides: Partial<MilestoneAchievement> = {}): MilestoneAchievement {
  return {
    id: 1,
    goal_id: 10,
    milestone_type: 'CONSECUTIVE_DAYS',
    milestone_key: '7',
    achieved_at: '2026-01-01T00:00:00',
    celebrated_at: null,
    ...overrides,
  }
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('useMilestoneCelebrationQueue', () => {
  it('has no current milestone initially', () => {
    const { result } = renderHook(() => useMilestoneCelebrationQueue())
    expect(result.current.current).toBeUndefined()
  })

  it('does nothing when goalId is null', async () => {
    const { result } = renderHook(() => useMilestoneCelebrationQueue())

    await act(async () => {
      await result.current.checkGoal(null, 'EXAM')
    })

    expect(milestonesApi.listPendingCelebrations).not.toHaveBeenCalled()
    expect(result.current.current).toBeUndefined()
  })

  it('silently ignores a failure while checking for new celebrations', async () => {
    vi.mocked(milestonesApi.listPendingCelebrations).mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useMilestoneCelebrationQueue())

    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })

    expect(result.current.current).toBeUndefined()
  })

  it('enqueues pending celebrations fetched for the goal', async () => {
    vi.mocked(milestonesApi.listPendingCelebrations).mockResolvedValue([makeAchievement()])
    const { result } = renderHook(() => useMilestoneCelebrationQueue())

    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })

    expect(result.current.current?.achievement.id).toBe(1)
    expect(result.current.current?.category).toBe('EXAM')
  })

  it('does not enqueue the same achievement twice', async () => {
    vi.mocked(milestonesApi.listPendingCelebrations).mockResolvedValue([makeAchievement()])
    const { result } = renderHook(() => useMilestoneCelebrationQueue())

    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })
    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })

    expect(result.current.current?.achievement.id).toBe(1)
  })

  it('dismissCurrent marks the current milestone celebrated and advances the queue', async () => {
    vi.mocked(milestonesApi.listPendingCelebrations).mockResolvedValue([
      makeAchievement({ id: 1 }),
      makeAchievement({ id: 2, milestone_key: '14' }),
    ])
    vi.mocked(milestonesApi.celebrateMilestone).mockResolvedValue(makeAchievement())
    const { result } = renderHook(() => useMilestoneCelebrationQueue())
    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })

    act(() => {
      result.current.dismissCurrent()
    })

    expect(milestonesApi.celebrateMilestone).toHaveBeenCalledWith(10, 1)
    expect(result.current.current?.achievement.id).toBe(2)
  })

  it('reports an error from dismissCurrent but still advances the queue', async () => {
    vi.mocked(milestonesApi.listPendingCelebrations).mockResolvedValue([makeAchievement()])
    vi.mocked(milestonesApi.celebrateMilestone).mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useMilestoneCelebrationQueue())
    await act(async () => {
      await result.current.checkGoal(10, 'EXAM')
    })

    const onError = vi.fn()
    act(() => {
      result.current.dismissCurrent(onError)
    })

    await waitFor(() => expect(onError).toHaveBeenCalled())
    expect(result.current.current).toBeUndefined()
  })
})
