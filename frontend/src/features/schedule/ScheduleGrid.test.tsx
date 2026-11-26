import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleGrid } from './ScheduleGrid'
import type { ScheduleDraft } from './scheduleDraftTypes'

const onMoveRow = vi.fn()
const onInsertRowBelow = vi.fn()
const onRemoveRow = vi.fn()
const onFieldChange = vi.fn()
const onStatusChange = vi.fn()
const onCellChange = vi.fn()
const onRenameColumn = vi.fn()
const onMoveColumn = vi.fn()
const onRemoveColumn = vi.fn()
const columnHasAnyValue = vi.fn().mockReturnValue(false)

function draft(itemCount: number): ScheduleDraft {
  return {
    revision: 1,
    columns: [],
    items: Array.from({ length: itemCount }, (_, index) => ({
      key: `id:${index + 1}`,
      id: index + 1,
      tempKey: null,
      title: `作業${index + 1}`,
      description: null,
      plannedStartDate: '2026-11-01',
      plannedEndDate: '2026-11-10',
      status: 'NOT_STARTED' as const,
      actualStartDate: null,
      actualEndDate: null,
      cells: {},
    })),
  }
}

function renderGrid(overrides: Partial<Parameters<typeof ScheduleGrid>[0]> = {}) {
  return render(
    <ScheduleGrid
      draft={draft(3)}
      readOnly={false}
      frozenRowCount={1}
      frozenColumnCount={1}
      today="2026-11-05"
      ganttDayWidthMinRem={1.75}
      ganttDayWidthMaxRem={4.5}
      holidayIsoDates={new Set()}
      holidayYearFrom={1955}
      holidayYearTo={2027}
      fieldErrorsByItemKey={{}}
      columnErrorsByKey={{}}
      columnHasAnyValue={columnHasAnyValue}
      goToTodaySignal={0}
      proposedBandByItemId={{}}
      onMoveRow={onMoveRow}
      onInsertRowBelow={onInsertRowBelow}
      onRemoveRow={onRemoveRow}
      onFieldChange={onFieldChange}
      onStatusChange={onStatusChange}
      onCellChange={onCellChange}
      onRenameColumn={onRenameColumn}
      onMoveColumn={onMoveColumn}
      onRemoveColumn={onRemoveColumn}
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

describe('ScheduleGrid', () => {
  it('全行を表示する', () => {
    renderGrid()
    expect(screen.getAllByTestId('schedule-data-row')).toHaveLength(3)
  })

  it('行の削除ボタンを押すと、その行のキーでonRemoveRowが呼ばれる', async () => {
    renderGrid()
    const deleteButtons = screen.getAllByRole('button', { name: t('schedule.rowActions.delete') })
    await userEvent.click(deleteButtons[1])
    expect(onRemoveRow).toHaveBeenCalledWith('id:2')
  })

  it('作業項目を編集すると、その行のキーでonFieldChangeが呼ばれる', async () => {
    renderGrid()
    const titleInputs = screen.getAllByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInputs[0], 'X')
    expect(onFieldChange).toHaveBeenCalledWith('id:1', 'title', expect.stringContaining('X'))
  })
})
