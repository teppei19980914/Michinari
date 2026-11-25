import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleDataRow } from './ScheduleDataRow'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

const onMoveUp = vi.fn()
const onMoveDown = vi.fn()
const onInsertBelow = vi.fn()
const onDelete = vi.fn()
const onFieldChange = vi.fn()
const onStatusChange = vi.fn()
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

function renderRow(overrides: Partial<Parameters<typeof ScheduleDataRow>[0]> = {}) {
  return render(
    <ScheduleDataRow
      item={item}
      customColumns={customColumns}
      readOnly={false}
      canMoveUp={true}
      canMoveDown={true}
      fieldErrors={undefined}
      rowActionsLeftRem={0}
      columnLeftOffsetsRem={[4.5, null, null, null, null, null, null, null]}
      rangeStartIso="2026-10-25"
      dayWidthRem={2}
      ganttWidthRem={40}
      today="2026-11-23"
      proposedBand={null}
      onMoveUp={onMoveUp}
      onMoveDown={onMoveDown}
      onInsertBelow={onInsertBelow}
      onDelete={onDelete}
      onFieldChange={onFieldChange}
      onStatusChange={onStatusChange}
      onCellChange={onCellChange}
      {...overrides}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ScheduleDataRow', () => {
  it('既定7列・追加列・ガントを1行として表示する', () => {
    renderRow()
    expect((screen.getByLabelText(t('schedule.columns.title')) as HTMLInputElement).value).toBe(
      '作業A',
    )
    expect((screen.getByLabelText('メモ') as HTMLInputElement).value).toBe('値1')
    expect(screen.getByTestId('planned-band')).not.toBe(null)
  })

  it('行操作ボタンから対応するハンドラが呼ばれる', async () => {
    renderRow()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.rowActions.moveUp') }))
    expect(onMoveUp).toHaveBeenCalledTimes(1)
  })

  it('閲覧のみの目標では行操作列が表示されない', () => {
    renderRow({ readOnly: true })
    expect(screen.queryByRole('button', { name: t('schedule.rowActions.moveUp') })).toBe(null)
  })

  it('未判断の修正案がある行は点線の帯を重ねて表示する（単位5・D-57）', () => {
    renderRow({ proposedBand: { start: '2026-11-15', end: '2026-11-20' } })
    expect(screen.getByTestId('proposed-band')).not.toBe(null)
  })

  it('修正案が無い行には点線の帯を表示しない', () => {
    renderRow({ proposedBand: null })
    expect(screen.queryByTestId('proposed-band')).toBe(null)
  })
})
