/** useScheduleRowActions の回帰テスト。カバレッジ閾値の対象外（vite.config.ts
 * `src/**\/use*.ts` 除外）だが、行の検索失敗時の無視（no-op）や状況変更時の補完呼び出しという
 * 非自明な分岐を持つため、OPERATIONS.md「フロントエンドのテストとカバレッジ」の方針に沿って
 * 直接テストする（独立レビュー指摘）。 */
import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { useScheduleRowActions } from './useScheduleRowActions'
import type { ScheduleDraft } from './scheduleDraftTypes'

function sampleDraft(): ScheduleDraft {
  return {
    revision: 1,
    columns: [],
    items: [
      {
        key: 'id:1',
        id: 1,
        tempKey: null,
        title: '作業A',
        description: null,
        plannedStartDate: '2026-11-01',
        plannedEndDate: '2026-11-10',
        status: 'NOT_STARTED',
        actualStartDate: null,
        actualEndDate: null,
        cells: {},
      },
      {
        key: 'id:2',
        id: 2,
        tempKey: null,
        title: '作業B',
        description: null,
        plannedStartDate: '2026-11-01',
        plannedEndDate: '2026-11-10',
        status: 'NOT_STARTED',
        actualStartDate: null,
        actualEndDate: null,
        cells: {},
      },
    ],
  }
}

function setup(initial: ScheduleDraft | null, today: string | null = '2026-11-23') {
  return renderHook(() => {
    const [draft, setDraft] = useState<ScheduleDraft | null>(initial)
    const actions = useScheduleRowActions(draft, setDraft, today)
    return { draft, ...actions }
  })
}

describe('useScheduleRowActions', () => {
  it('addRowは本日の日付で新しい行を追加する', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.addRow())
    expect(result.current.draft?.items).toHaveLength(3)
    const newItem = result.current.draft?.items[2]
    expect(newItem?.plannedStartDate).toBe('2026-11-23')
    expect(newItem?.id).toBeNull()
    expect(newItem?.tempKey).not.toBeNull()
  })

  it('insertRowBelowは指定した行の直下に挿入する', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.insertRowBelow('id:1'))
    expect(result.current.draft?.items.map((item) => item.key)).toEqual([
      'id:1',
      expect.stringContaining('temp:'),
      'id:2',
    ])
  })

  it('存在しない行キーに対するinsertRowBelow/moveRow/removeRowは何もしない', () => {
    const { result } = setup(sampleDraft())
    act(() => {
      result.current.insertRowBelow('id:999')
      result.current.moveRow('id:999', 1)
      result.current.removeRow('id:999')
    })
    expect(result.current.draft?.items).toHaveLength(2)
  })

  it('moveRowは行の並び順を入れ替える', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.moveRow('id:2', -1))
    expect(result.current.draft?.items.map((item) => item.key)).toEqual(['id:2', 'id:1'])
  })

  it('removeRowは指定した行を取り除く', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.removeRow('id:1'))
    expect(result.current.draft?.items.map((item) => item.key)).toEqual(['id:2'])
  })

  it('changeStatusはdraftがnullのときは何もしない', () => {
    const { result } = setup(null)
    act(() => result.current.changeStatus('id:1', 'DONE'))
    expect(result.current.draft).toBeNull()
  })

  it('changeStatusはtodayがnullのときは何もしない', () => {
    const { result } = setup(sampleDraft(), null)
    act(() => result.current.changeStatus('id:1', 'DONE'))
    expect(result.current.draft?.items[0].status).toBe('NOT_STARTED')
  })

  it('changeStatusは存在しない行キーのときは何もしない', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.changeStatus('id:999', 'DONE'))
    expect(result.current.draft?.items[0].status).toBe('NOT_STARTED')
  })

  it('changeStatusは状況と実績日の補完を同時に反映する', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.changeStatus('id:1', 'IN_PROGRESS'))
    const item = result.current.draft?.items[0]
    expect(item?.status).toBe('IN_PROGRESS')
    expect(item?.actualStartDate).toBe('2026-11-23')
  })

  it('updateCellは指定した行・列の値だけを更新する', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.updateCell('id:1', 'id:5', '新しい値'))
    expect(result.current.draft?.items[0].cells).toEqual({ 'id:5': '新しい値' })
    expect(result.current.draft?.items[1].cells).toEqual({})
  })
})
