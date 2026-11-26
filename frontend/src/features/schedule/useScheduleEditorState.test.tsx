/** useScheduleEditorState の回帰テスト。カバレッジ閾値の対象外（vite.config.ts
 * `src/**\/use*.ts` 除外）だが、一括保存・409の競合・固定設定の即時保存という非自明な
 * 分岐を持つため、OPERATIONS.md「フロントエンドのテストとカバレッジ」の方針に沿って
 * 直接テストする。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'
import type { ScheduleRead } from '../../api/schedule'
import { useScheduleEditorState } from './useScheduleEditorState'

const getSchedule = vi.hoisted(() => vi.fn())
const saveSchedule = vi.hoisted(() => vi.fn())
const updateScheduleViewSetting = vi.hoisted(() => vi.fn())
vi.mock('../../api/schedule', () => ({ getSchedule, saveSchedule, updateScheduleViewSetting }))

function sampleScheduleRead(overrides: Partial<ScheduleRead> = {}): ScheduleRead {
  return {
    revision: 1,
    frozen_row_count: 0,
    frozen_column_count: 1,
    today: '2026-11-23',
    max_items: 100,
    max_custom_columns: 10,
    gantt_day_width_min_rem: 1.75,
    gantt_day_width_max_rem: 4.5,
    columns: [],
    items: [
      {
        id: 10,
        title: '作業A',
        description: null,
        planned_start_date: '2026-11-01',
        planned_end_date: '2026-11-10',
        status: 'NOT_STARTED',
        actual_start_date: null,
        actual_end_date: null,
        display_order: 0,
        cells: [],
      },
    ],
    pending_revision_proposal: null,
    ...overrides,
  }
}

function setup(goalId = 1, readOnly = false) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useScheduleEditorState(goalId, readOnly), { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useScheduleEditorState の初期読み込み', () => {
  it('取得したデータからdraftを組み立てる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { result } = setup()

    await waitFor(() => expect(result.current.draft).not.toBe(null))

    expect(result.current.draft?.items[0].title).toBe('作業A')
    expect(result.current.hasUnsavedChanges).toBe(false)
    expect(result.current.today).toBe('2026-11-23')
  })
})

describe('useScheduleEditorState の編集操作', () => {
  it('行を追加すると未保存になる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.addRow()
    })

    expect(result.current.draft?.items).toHaveLength(2)
    expect(result.current.hasUnsavedChanges).toBe(true)
  })

  it('状況を進行中へ変更すると実績開始日が本日で補完される（6.3）', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.changeStatus('id:10', 'IN_PROGRESS')
    })

    const item = result.current.draft?.items.find((candidate) => candidate.key === 'id:10')
    expect(item?.actualStartDate).toBe('2026-11-23')
  })

  it('作業項目が空白のみの行があると保存できない（検証エラー）', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.updateItem('id:10', { title: '   ' })
    })
    expect(result.current.hasFieldErrors).toBe(true)

    act(() => {
      result.current.save()
    })
    expect(saveSchedule).not.toHaveBeenCalled()
  })

  it('破棄すると最後に保存された状態へ戻る', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.updateItem('id:10', { title: '編集後' })
    })
    expect(result.current.hasUnsavedChanges).toBe(true)

    act(() => {
      result.current.discard()
    })
    expect(result.current.draft?.items[0].title).toBe('作業A')
    expect(result.current.hasUnsavedChanges).toBe(false)
  })
})

describe('useScheduleEditorState の保存', () => {
  it('保存に成功するとdraft・baselineの両方をサーバー応答へ揃える', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const saved = sampleScheduleRead({ revision: 2 })
    saveSchedule.mockResolvedValue(saved)
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    await act(async () => {
      result.current.save()
    })

    await waitFor(() => expect(result.current.draft?.revision).toBe(2))
    expect(result.current.hasUnsavedChanges).toBe(false)
  })

  it('409（版数の不一致）では編集内容を破棄せずconflictを立てる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    saveSchedule.mockRejectedValue(new ApiError('SCHEDULE_REVISION_CONFLICT', '競合しました'))
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.updateItem('id:10', { title: '編集中' })
    })

    await act(async () => {
      result.current.save()
    })

    await waitFor(() => expect(result.current.conflict).toBe(true))
    expect(result.current.draft?.items[0].title).toBe('編集中')
  })

  it('最新を読み込むと最新データへ揃えてconflictを閉じる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    saveSchedule.mockRejectedValue(new ApiError('SCHEDULE_REVISION_CONFLICT', '競合しました'))
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    act(() => {
      result.current.updateItem('id:10', { title: '編集中' })
    })
    await act(async () => {
      result.current.save()
    })
    await waitFor(() => expect(result.current.conflict).toBe(true))

    getSchedule.mockResolvedValue(sampleScheduleRead({ revision: 5 }))
    await act(async () => {
      await result.current.resolveConflictReload()
    })

    expect(result.current.conflict).toBe(false)
    expect(result.current.draft?.revision).toBe(5)
    expect(result.current.draft?.items[0].title).toBe('作業A')
  })
})

describe('useScheduleEditorState の固定設定', () => {
  it('固定行数・列数の変更は即時に別APIで保存し、未保存の判定に影響しない', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    updateScheduleViewSetting.mockResolvedValue({ frozen_row_count: 2, frozen_column_count: 3 })
    const { result } = setup()
    await waitFor(() => expect(result.current.draft).not.toBe(null))

    await act(async () => {
      result.current.updateFrozenCounts(2, 3)
    })

    expect(updateScheduleViewSetting).toHaveBeenCalledWith(1, {
      frozen_row_count: 2,
      frozen_column_count: 3,
    })
    await waitFor(() => expect(result.current.frozenRowCount).toBe(2))
    expect(result.current.hasUnsavedChanges).toBe(false)
  })
})
