import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleFixedColumnsHeader } from './ScheduleFixedColumnsHeader'

const onRenameColumn = vi.fn()
const onMoveColumn = vi.fn()
const onRemoveColumn = vi.fn()
const columnHasAnyValue = vi.fn().mockReturnValue(false)

const customColumns = [
  { key: 'id:5', id: 5, tempKey: null, name: 'メモ' },
  { key: 'id:6', id: 6, tempKey: null, name: '優先度' },
]

function renderHeader(overrides: Partial<Parameters<typeof ScheduleFixedColumnsHeader>[0]> = {}) {
  return render(
    <ScheduleFixedColumnsHeader
      customColumns={customColumns}
      readOnly={false}
      rowActionsLeftRem={0}
      columnLeftOffsetsRem={[4.5, null, null, null, null, null, null, null, null]}
      columnErrorsByKey={{}}
      columnHasAnyValue={columnHasAnyValue}
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

describe('ScheduleFixedColumnsHeader', () => {
  it('既定7列のラベルと追加列の名前を表示する', () => {
    renderHeader()
    expect(screen.getByText(t('schedule.columns.title'))).not.toBe(null)
    expect(screen.getByText(t('schedule.columns.actualEndDate'))).not.toBe(null)
    const renameInputs = screen.getAllByLabelText(
      t('schedule.customColumn.renameLabel'),
    ) as HTMLInputElement[]
    expect(renameInputs.map((input) => input.value)).toEqual(['メモ', '優先度'])
  })

  it('最初の追加列は左へ移動できない、最後の追加列は右へ移動できない', () => {
    renderHeader()
    const leftButtons = screen.getAllByRole('button', {
      name: t('schedule.customColumn.moveLeft'),
    }) as HTMLButtonElement[]
    const rightButtons = screen.getAllByRole('button', {
      name: t('schedule.customColumn.moveRight'),
    }) as HTMLButtonElement[]
    expect(leftButtons[0].disabled).toBe(true)
    expect(rightButtons[1].disabled).toBe(true)
  })

  it('移動できる方向のボタンを押すとonMoveColumnが呼ばれる', async () => {
    renderHeader()
    const leftButtons = screen.getAllByRole('button', {
      name: t('schedule.customColumn.moveLeft'),
    })
    const rightButtons = screen.getAllByRole('button', {
      name: t('schedule.customColumn.moveRight'),
    })
    await userEvent.click(leftButtons[1])
    await userEvent.click(rightButtons[0])
    expect(onMoveColumn).toHaveBeenNthCalledWith(1, 'id:6', -1)
    expect(onMoveColumn).toHaveBeenNthCalledWith(2, 'id:5', 1)
  })

  it('名前を変更するとonRenameColumnが呼ばれる', async () => {
    renderHeader()
    const renameInputs = screen.getAllByLabelText(t('schedule.customColumn.renameLabel'))
    await userEvent.type(renameInputs[0], 'X')
    expect(onRenameColumn).toHaveBeenCalledWith('id:5', expect.stringContaining('X'))
  })

  it('列の削除ボタンでonRemoveColumnが呼ばれる', async () => {
    renderHeader()
    const deleteButtons = screen.getAllByRole('button', {
      name: t('schedule.customColumn.delete'),
    })
    await userEvent.click(deleteButtons[0])
    expect(onRemoveColumn).toHaveBeenCalledWith('id:5')
  })
})
