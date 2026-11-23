import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleDefaultCells } from './ScheduleDefaultCells'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

const onFieldChange = vi.fn()
const onStatusChange = vi.fn()

function baseItem(overrides: Partial<ScheduleDraftItem> = {}): ScheduleDraftItem {
  return {
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
    ...overrides,
  }
}

function renderCells(overrides: Partial<ScheduleDraftItem> = {}) {
  return render(
    <ScheduleDefaultCells
      item={baseItem(overrides)}
      readOnly={false}
      errors={{}}
      leftOffsetsRem={[null, null, null, null, null, null, null]}
      onFieldChange={onFieldChange}
      onStatusChange={onStatusChange}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleDefaultCells', () => {
  it('作業項目を変更するとonFieldChangeが呼ばれる', async () => {
    renderCells()
    const titleInput = screen.getByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')
    expect(onFieldChange).toHaveBeenCalledWith('title', expect.stringContaining('X'))
  })

  it('作業項目のエラーがあれば文言を表示する', () => {
    render(
      <ScheduleDefaultCells
        item={baseItem()}
        readOnly={false}
        errors={{ title: 'TITLE_REQUIRED' }}
        leftOffsetsRem={[null, null, null, null, null, null, null]}
        onFieldChange={onFieldChange}
        onStatusChange={onStatusChange}
      />,
    )
    expect(screen.getByText(t('schedule.validation.TITLE_REQUIRED'))).not.toBe(null)
  })

  it('未着手では実績開始日が無効、進行中では実績開始日のみ有効、完了では両方有効', () => {
    const { unmount } = renderCells({ status: 'NOT_STARTED' })
    expect((screen.getByLabelText(t('schedule.columns.actualStartDate')) as HTMLInputElement).disabled).toBe(true)
    unmount()

    renderCells({ status: 'IN_PROGRESS' })
    expect((screen.getByLabelText(t('schedule.columns.actualStartDate')) as HTMLInputElement).disabled).toBe(false)
    expect((screen.getByLabelText(t('schedule.columns.actualEndDate')) as HTMLInputElement).disabled).toBe(true)
  })

  it('作業内容を変更するとonFieldChangeが呼ばれる', async () => {
    renderCells()
    const descriptionInput = screen.getByLabelText(t('schedule.columns.description'))
    await userEvent.type(descriptionInput, 'X')
    expect(onFieldChange).toHaveBeenCalledWith('description', expect.stringContaining('X'))
  })

  it('予定開始日・予定終了日を変更するとonFieldChangeが呼ばれる', async () => {
    renderCells()
    const startInput = screen.getByLabelText(t('schedule.columns.plannedStartDate'))
    await userEvent.clear(startInput)
    expect(onFieldChange).toHaveBeenCalledWith('plannedStartDate', null)

    const endInput = screen.getByLabelText(t('schedule.columns.plannedEndDate'))
    await userEvent.clear(endInput)
    expect(onFieldChange).toHaveBeenCalledWith('plannedEndDate', null)
  })

  it('実績開始日・実績終了日を変更するとonFieldChangeが呼ばれる', async () => {
    renderCells({ status: 'DONE', actualStartDate: '2026-11-02', actualEndDate: '2026-11-03' })
    const startInput = screen.getByLabelText(t('schedule.columns.actualStartDate'))
    await userEvent.clear(startInput)
    expect(onFieldChange).toHaveBeenCalledWith('actualStartDate', null)

    const endInput = screen.getByLabelText(t('schedule.columns.actualEndDate'))
    await userEvent.clear(endInput)
    expect(onFieldChange).toHaveBeenCalledWith('actualEndDate', null)
  })

  it('状況を変えるとonStatusChangeが呼ばれる', async () => {
    renderCells()
    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.columns.status')),
      t('schedule.status.DONE'),
    )
    expect(onStatusChange).toHaveBeenCalledWith('DONE')
  })

  it('readOnlyのとき全セルがdisabledになる', () => {
    render(
      <ScheduleDefaultCells
        item={baseItem()}
        readOnly={true}
        errors={{}}
        leftOffsetsRem={[null, null, null, null, null, null, null]}
        onFieldChange={onFieldChange}
        onStatusChange={onStatusChange}
      />,
    )
    expect((screen.getByLabelText(t('schedule.columns.title')) as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByLabelText(t('schedule.columns.status')) as HTMLSelectElement).disabled).toBe(true)
  })
})
