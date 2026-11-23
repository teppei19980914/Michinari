import { describe, expect, it } from 'vitest'
import type { ScheduleRead } from '../../api/schedule'
import { buildSaveRequest, columnKey, draftContentEquals, toDraft } from './scheduleDraftTypes'

function sampleScheduleRead(): ScheduleRead {
  return {
    revision: 3,
    frozen_row_count: 1,
    frozen_column_count: 2,
    today: '2026-11-23',
    max_items: 100,
    max_custom_columns: 10,
    gantt_day_width_min_rem: 1.75,
    gantt_day_width_max_rem: 4.5,
    columns: [{ id: 5, name: 'メモ', display_order: 0 }],
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
        cells: [{ column_id: 5, value: '値1' }],
      },
    ],
  }
}

describe('columnKey', () => {
  it('idがあればid:接頭辞のキーを返す', () => {
    expect(columnKey(5, null)).toBe('id:5')
  })

  it('idが無ければtemp:接頭辞のキーを返す', () => {
    expect(columnKey(null, 'row-1')).toBe('temp:row-1')
  })
})

describe('toDraft', () => {
  it('サーバー応答をドラフト形式へ変換する（セルはcolumn_idキーのマップになる）', () => {
    const draft = toDraft(sampleScheduleRead())
    expect(draft.revision).toBe(3)
    expect(draft.columns).toEqual([{ key: 'id:5', id: 5, tempKey: null, name: 'メモ' }])
    expect(draft.items[0].key).toBe('id:10')
    expect(draft.items[0].cells).toEqual({ 'id:5': '値1' })
  })
})

describe('buildSaveRequest', () => {
  it('既存の行・列はidで、新規はtemp_keyで送る', () => {
    const draft = toDraft(sampleScheduleRead())
    draft.columns.push({ key: 'temp:col-1', id: null, tempKey: 'col-1', name: '新しい列' })
    draft.items.push({
      key: 'temp:row-1',
      id: null,
      tempKey: 'row-1',
      title: '作業B',
      description: null,
      plannedStartDate: '2026-11-05',
      plannedEndDate: '2026-11-06',
      status: 'NOT_STARTED',
      actualStartDate: null,
      actualEndDate: null,
      cells: { 'id:5': '', 'temp:col-1': '新しい値' },
    })

    const request = buildSaveRequest(draft)
    expect(request.revision).toBe(3)
    expect(request.columns).toEqual([
      { id: 5, name: 'メモ' },
      { temp_key: 'col-1', name: '新しい列' },
    ])
    expect(request.items?.[0]).toMatchObject({ id: 10, title: '作業A' })
    // item[0]は新しい列(temp:col-1)のセルを持たないため、送信時は空文字で埋められる。
    expect(request.items?.[0].cells).toEqual([
      { column_id: 5, value: '値1' },
      { column_temp_key: 'col-1', value: '' },
    ])
    expect(request.items?.[1]).toMatchObject({ id: undefined, title: '作業B' })
    expect(request.items?.[1].cells).toEqual([
      { column_id: 5, value: '' },
      { column_temp_key: 'col-1', value: '新しい値' },
    ])
  })

  it('id列の値が無い行は空文字で送る', () => {
    const draft = toDraft(sampleScheduleRead())
    draft.items[0].cells = {}

    const request = buildSaveRequest(draft)
    expect(request.items?.[0].cells).toEqual([{ column_id: 5, value: '' }])
  })
})

describe('draftContentEquals', () => {
  it('同じcolumns・itemsなら等しいと判定する', () => {
    const a = toDraft(sampleScheduleRead())
    const b = toDraft(sampleScheduleRead())
    expect(draftContentEquals(a, b)).toBe(true)
  })

  it('revisionだけが異なる場合は比較対象にしない', () => {
    const a = toDraft(sampleScheduleRead())
    const b = { ...toDraft(sampleScheduleRead()), revision: 99 }
    expect(draftContentEquals(a, b)).toBe(true)
  })

  it('itemsの内容が異なれば等しくないと判定する', () => {
    const a = toDraft(sampleScheduleRead())
    const b = toDraft(sampleScheduleRead())
    b.items[0].title = '作業A（編集済み）'
    expect(draftContentEquals(a, b)).toBe(false)
  })
})
