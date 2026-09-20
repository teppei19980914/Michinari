/** 今日の一言の表示条件を固定する（Phase 35）。
 *
 * この欄はAIの生成を待つため他の要素と独立して非同期に取得する。生成できなかったときに
 * 空のカードが残ると「何かを待っている」ように見えてしまうため、該当がないときと失敗したときは
 * 何も描かないことを固定する。複数目標が同時進行する場合は目標ごとに生成されるため、
 * 選択中の目標の分だけを出す（Phase25）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID } from '../../test/fixtures'
import { TodayMessage } from './TodayMessage'

const getDailyMessage = vi.hoisted(() => vi.fn())
vi.mock('../../api/records', () => ({ getDailyMessage }))

const OTHER_GOAL_ID = GOAL_ID + 1

function message(goalId: number | null, body: string, isFallback = false) {
  return {
    target_date: '2026-09-13',
    goal_id: goalId,
    goal_name: goalId === null ? null : '目標A',
    body,
    generated_at: '2026-09-13T00:00:00',
    is_fallback: isFallback,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getDailyMessage.mockResolvedValue([message(GOAL_ID, '今日もいい調子です')])
})

afterEach(() => {
  cleanup()
})

describe('TodayMessage', () => {
  it('shows the loading text while the message is being fetched', () => {
    getDailyMessage.mockReturnValue(new Promise(() => undefined))
    renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    expect(screen.getByText(t('dashboard.todayMessage.loading'))).toBeDefined()
  })

  it('shows the message generated for the selected goal', async () => {
    renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    expect(await screen.findByText('今日もいい調子です')).toBeDefined()
  })

  it('renders nothing when the message belongs to another goal', async () => {
    getDailyMessage.mockResolvedValue([message(OTHER_GOAL_ID, '別目標の一言')])
    const { container } = renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('renders nothing when there is no message at all', async () => {
    getDailyMessage.mockResolvedValue([])
    const { container } = renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('renders nothing when fetching fails', async () => {
    // 一言は補助的な表示であり、取得できないことを利用者へ伝える価値がない。AI未設定は
    // バックエンドが200+is_fallbackで返すためここには到達しない（下のテスト参照）。
    // ここに来るのはAI基盤側の障害等の想定外の失敗のみで、静かに何も出さない。
    getDailyMessage.mockRejectedValue(new Error('boom'))
    const { container } = renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('shows the fixed fallback message when AI is not configured', async () => {
    // AI未設定時はバックエンドがエラーではなく200 + is_fallback=trueで返す（S-4 4-1）。
    getDailyMessage.mockResolvedValue([message(GOAL_ID, '', true)])
    renderWithProviders(<TodayMessage goalId={GOAL_ID} />)

    expect(await screen.findByText(t('dashboard.todayMessage.fallback'))).toBeDefined()
  })

  it('shows the goal independent message when no goal is selected', async () => {
    getDailyMessage.mockResolvedValue([message(null, '目標によらない一言')])
    renderWithProviders(<TodayMessage goalId={null} />)

    expect(await screen.findByText('目標によらない一言')).toBeDefined()
  })
})
