import { describe, expect, it, vi } from 'vitest'
import { buildScheduleRowProps } from './buildScheduleRowProps'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

const item: ScheduleDraftItem = {
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
}

function baseParams(overrides: Partial<Parameters<typeof buildScheduleRowProps>[0]> = {}) {
  return {
    item,
    index: 1,
    itemCount: 3,
    customColumns: [],
    readOnly: false,
    fieldErrorsByItemKey: {},
    rowActionsLeftRem: 0,
    columnLeftOffsetsRem: [],
    rangeStartIso: '2026-10-25',
    dayWidthRem: 2,
    ganttWidthRem: 40,
    today: '2026-11-23',
    onMoveRow: vi.fn(),
    onInsertRowBelow: vi.fn(),
    onRemoveRow: vi.fn(),
    onFieldChange: vi.fn(),
    onStatusChange: vi.fn(),
    onCellChange: vi.fn(),
    ...overrides,
  }
}

describe('buildScheduleRowProps', () => {
  it('先頭でも末尾でもない行はcanMoveUp・canMoveDownの両方がtrue', () => {
    const props = buildScheduleRowProps(baseParams({ index: 1, itemCount: 3 }))
    expect(props.canMoveUp).toBe(true)
    expect(props.canMoveDown).toBe(true)
  })

  it('先頭行はcanMoveUpがfalse、末尾行はcanMoveDownがfalse', () => {
    const first = buildScheduleRowProps(baseParams({ index: 0, itemCount: 3 }))
    const last = buildScheduleRowProps(baseParams({ index: 2, itemCount: 3 }))
    expect(first.canMoveUp).toBe(false)
    expect(last.canMoveDown).toBe(false)
  })

  it('onInsertBelow/onDeleteはitem.keyを添えて転送する', () => {
    const onInsertRowBelow = vi.fn()
    const onRemoveRow = vi.fn()
    const props = buildScheduleRowProps(baseParams({ onInsertRowBelow, onRemoveRow }))
    props.onInsertBelow()
    props.onDelete()
    expect(onInsertRowBelow).toHaveBeenCalledWith('id:1')
    expect(onRemoveRow).toHaveBeenCalledWith('id:1')
  })

  it('onMoveUp/onMoveDownはitem.keyとoffsetを添えてonMoveRowを呼ぶ', () => {
    const onMoveRow = vi.fn()
    const props = buildScheduleRowProps(baseParams({ onMoveRow }))
    props.onMoveUp()
    props.onMoveDown()
    expect(onMoveRow).toHaveBeenNthCalledWith(1, 'id:1', -1)
    expect(onMoveRow).toHaveBeenNthCalledWith(2, 'id:1', 1)
  })

  it('onFieldChange/onStatusChange/onCellChangeはitem.keyを添えて転送する', () => {
    const onFieldChange = vi.fn()
    const onStatusChange = vi.fn()
    const onCellChange = vi.fn()
    const props = buildScheduleRowProps(baseParams({ onFieldChange, onStatusChange, onCellChange }))

    props.onFieldChange('title', '新しい値')
    props.onStatusChange('DONE')
    props.onCellChange('id:5', '値')

    expect(onFieldChange).toHaveBeenCalledWith('id:1', 'title', '新しい値')
    expect(onStatusChange).toHaveBeenCalledWith('id:1', 'DONE')
    expect(onCellChange).toHaveBeenCalledWith('id:1', 'id:5', '値')
  })

  it('fieldErrorsByItemKeyからこの行のエラーだけを取り出す', () => {
    const props = buildScheduleRowProps(
      baseParams({ fieldErrorsByItemKey: { 'id:1': { title: 'TITLE_REQUIRED' } } }),
    )
    expect(props.fieldErrors).toEqual({ title: 'TITLE_REQUIRED' })
  })
})
