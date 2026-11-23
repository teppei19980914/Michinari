import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScheduleCustomValueCells } from './ScheduleCustomValueCells'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

const onCellChange = vi.fn()

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
  cells: { 'id:5': '値1' },
}

const customColumns = [{ key: 'id:5', id: 5, tempKey: null, name: 'メモ' }]

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleCustomValueCells', () => {
  it('列ごとの値をラベル（列名）付きで表示する', () => {
    render(
      <ScheduleCustomValueCells
        item={item}
        customColumns={customColumns}
        readOnly={false}
        columnLeftOffsetsRem={[null, null, null, null, null, null, null, null]}
        onCellChange={onCellChange}
      />,
    )
    expect((screen.getByLabelText('メモ') as HTMLInputElement).value).toBe('値1')
  })

  it('値を変更するとonCellChangeへ列キーと値を渡す', async () => {
    render(
      <ScheduleCustomValueCells
        item={item}
        customColumns={customColumns}
        readOnly={false}
        columnLeftOffsetsRem={[null, null, null, null, null, null, null, null]}
        onCellChange={onCellChange}
      />,
    )
    await userEvent.type(screen.getByLabelText('メモ'), 'X')
    expect(onCellChange).toHaveBeenCalledWith('id:5', expect.stringContaining('X'))
  })

  it('列が固定対象（leftRemが非null）のときはsticky表示にする', () => {
    const { container } = render(
      <ScheduleCustomValueCells
        item={item}
        customColumns={customColumns}
        readOnly={false}
        columnLeftOffsetsRem={[null, null, null, null, null, null, null, 11.5]}
        onCellChange={onCellChange}
      />,
    )
    expect((container.firstChild as HTMLElement).style.position).toBe('sticky')
  })

  it('readOnlyではdisabledになる', () => {
    render(
      <ScheduleCustomValueCells
        item={item}
        customColumns={customColumns}
        readOnly={true}
        columnLeftOffsetsRem={[null, null, null, null, null, null, null, null]}
        onCellChange={onCellChange}
      />,
    )
    expect((screen.getByLabelText('メモ') as HTMLInputElement).disabled).toBe(true)
  })

  it('値が無い列は空文字で表示する', () => {
    const itemWithoutCell = { ...item, cells: {} }
    render(
      <ScheduleCustomValueCells
        item={itemWithoutCell}
        customColumns={customColumns}
        readOnly={false}
        columnLeftOffsetsRem={[null, null, null, null, null, null, null, null]}
        onCellChange={onCellChange}
      />,
    )
    expect((screen.getByLabelText('メモ') as HTMLInputElement).value).toBe('')
  })

  it('追加列が0件なら何も描画しない', () => {
    const { container } = render(
      <ScheduleCustomValueCells
        item={item}
        customColumns={[]}
        readOnly={false}
        columnLeftOffsetsRem={[]}
        onCellChange={onCellChange}
      />,
    )
    expect(container.textContent).toBe('')
  })
})
