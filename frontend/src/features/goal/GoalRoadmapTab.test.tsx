/** 目標詳細「道のり」タブの読み込み中・エラー・成功の3状態を固定する（開発Todo_道のりマップ_v1.0.md
 * §3.4 F-03）。ReplanHistoryTab等と同じuseQuery＋状態表示の構成（CODING_RULES.md ①DRYの原則）。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GoalRoadmapTab } from './GoalRoadmapTab'
import type { GoalRoadmapRead } from '../../api/goals'

const getGoalRoadmap = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ getGoalRoadmap }))

const GOAL_ID = 1

function makeRoadmap(overrides: Partial<GoalRoadmapRead> = {}): GoalRoadmapRead {
  return {
    category: 'EXAM',
    start_date: '2026-01-01',
    goal_date: '2026-01-11',
    today_date: '2026-01-06',
    progress_ratio: 0.5,
    is_achieved: false,
    planned_points: [],
    actual_points: [],
    footprint_dates: [],
    replan_marks: [],
    feedback_marks: [],
    buffer_dates: [],
    overrun_days: null,
    ...overrides,
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('GoalRoadmapTab', () => {
  it('読み込み中は読み込み中の文言を表示する', () => {
    getGoalRoadmap.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<GoalRoadmapTab goalId={GOAL_ID} />)
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })

  it('取得失敗時はエラー文言を表示する', async () => {
    getGoalRoadmap.mockRejectedValue(new Error('network error'))
    renderWithProviders(<GoalRoadmapTab goalId={GOAL_ID} />)
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })

  it('取得成功時は道のりの図（role="img"）を表示する', async () => {
    getGoalRoadmap.mockResolvedValue(makeRoadmap())
    renderWithProviders(<GoalRoadmapTab goalId={GOAL_ID} />)
    expect(await screen.findByRole('img')).toBeTruthy()
  })
})
