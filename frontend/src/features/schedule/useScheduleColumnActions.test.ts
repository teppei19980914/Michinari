/** useScheduleColumnActions の回帰テスト。カバレッジ閾値の対象外（vite.config.ts
 * `src/**\/use*.ts` 除外）だが、列の検索失敗時の無視（no-op）や新しい列を既存行へ
 * 空文字で広げる処理という非自明な分岐を持つため、OPERATIONS.md「フロントエンドのテストと
 * カバレッジ」の方針に沿って直接テストする（独立レビュー指摘）。 */
import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { useScheduleColumnActions } from './useScheduleColumnActions'
import type { ScheduleDraft } from './scheduleDraftTypes'

function sampleDraft(): ScheduleDraft {
  return {
    revision: 1,
    columns: [
      { key: 'id:5', id: 5, tempKey: null, name: 'メモ' },
      { key: 'id:6', id: 6, tempKey: null, name: '優先度' },
    ],
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
        cells: { 'id:5': '値1' },
      },
    ],
  }
}

function setup(initial: ScheduleDraft | null) {
  return renderHook(() => {
    const [draft, setDraft] = useState<ScheduleDraft | null>(initial)
    const actions = useScheduleColumnActions(draft, setDraft)
    return { draft, ...actions }
  })
}

describe('useScheduleColumnActions', () => {
  it('addColumnは新しい列を追加し、既存の全行に空文字のセルを広げる', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.addColumn())
    expect(result.current.draft?.columns).toHaveLength(3)
    const newColumn = result.current.draft?.columns[2]
    expect(newColumn?.id).toBeNull()
    expect(result.current.draft?.items[0].cells[newColumn!.key]).toBe('')
  })

  it('renameColumnは指定した列の名前だけを変更する', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.renameColumn('id:5', '新しい名前'))
    expect(result.current.draft?.columns[0].name).toBe('新しい名前')
    expect(result.current.draft?.columns[1].name).toBe('優先度')
  })

  it('moveColumnは列の並び順を入れ替える', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.moveColumn('id:6', -1))
    expect(result.current.draft?.columns.map((c) => c.key)).toEqual(['id:6', 'id:5'])
  })

  it('存在しない列キーに対するmoveColumnは何もしない', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.moveColumn('id:999', -1))
    expect(result.current.draft?.columns.map((c) => c.key)).toEqual(['id:5', 'id:6'])
  })

  it('removeColumnは指定した列を取り除く', () => {
    const { result } = setup(sampleDraft())
    act(() => result.current.removeColumn('id:5'))
    expect(result.current.draft?.columns.map((c) => c.key)).toEqual(['id:6'])
  })

  it('columnHasAnyValueは値を持つ行が1件でもあればtrueを返す', () => {
    const { result } = setup(sampleDraft())
    expect(result.current.columnHasAnyValue('id:5')).toBe(true)
    expect(result.current.columnHasAnyValue('id:6')).toBe(false)
  })

  it('draftがnullのときcolumnHasAnyValueはfalseを返す', () => {
    const { result } = setup(null)
    expect(result.current.columnHasAnyValue('id:5')).toBe(false)
  })
})
