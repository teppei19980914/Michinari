import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleItemRow } from './ScheduleItemRow'
import type { ScheduleItemForReportRead } from '../../api/records'
import type { ScheduleItemDraftValue } from './scheduleItemsDraft'

const ITEM: ScheduleItemForReportRead = {
  id: 1,
  title: '第1章',
  planned_start_date: '2026-11-01',
  planned_end_date: '2026-11-10',
  status: 'NOT_STARTED',
  actual_start_date: null,
  actual_end_date: null,
  default_visible: true,
}

const VALUE: ScheduleItemDraftValue = {
  status: 'NOT_STARTED',
  actualStartDate: null,
  actualEndDate: null,
  touched: false,
}

const onChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleItemRow（editable）', () => {
  it('shows the title and planned period', () => {
    render(
      <ScheduleItemRow item={ITEM} targetDate="2026-11-05" readOnly={false} value={VALUE} onChange={onChange} />,
    )
    expect(screen.getByText('第1章')).toBeTruthy()
    expect(
      screen.getByText(
        t('schedule.gantt.tooltip.planned', { start: '2026-11-01', end: '2026-11-10' }),
      ),
    ).toBeTruthy()
  })

  it('disables the actual date inputs while NOT_STARTED', () => {
    render(
      <ScheduleItemRow item={ITEM} targetDate="2026-11-05" readOnly={false} value={VALUE} onChange={onChange} />,
    )
    expect(
      (screen.getByLabelText(t('schedule.columns.actualStartDate')) as HTMLInputElement).disabled,
    ).toBe(true)
    expect(
      (screen.getByLabelText(t('schedule.columns.actualEndDate')) as HTMLInputElement).disabled,
    ).toBe(true)
  })

  it('applies the status auto-fill (基準日=targetDate) and marks the row touched', async () => {
    const user = userEvent.setup()
    render(
      <ScheduleItemRow item={ITEM} targetDate="2026-11-05" readOnly={false} value={VALUE} onChange={onChange} />,
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: t('schedule.columns.status') }),
      t('schedule.status.IN_PROGRESS'),
    )
    expect(onChange).toHaveBeenCalledWith({
      status: 'IN_PROGRESS',
      actualStartDate: '2026-11-05',
      actualEndDate: null,
      touched: true,
    })
  })

  it('edits the actual start date directly and marks the row touched', async () => {
    const user = userEvent.setup()
    const inProgress: ScheduleItemDraftValue = {
      status: 'IN_PROGRESS',
      actualStartDate: '2026-11-02',
      actualEndDate: null,
      touched: false,
    }
    render(
      <ScheduleItemRow
        item={{ ...ITEM, status: 'IN_PROGRESS' }}
        targetDate="2026-11-05"
        readOnly={false}
        value={inProgress}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText(t('schedule.columns.actualStartDate'))
    await user.clear(input)
    expect(onChange).toHaveBeenLastCalledWith({
      status: 'IN_PROGRESS',
      actualStartDate: null,
      actualEndDate: null,
      touched: true,
    })
  })

  it('enables both actual date inputs once DONE, and edits the actual end date', async () => {
    const user = userEvent.setup()
    const done: ScheduleItemDraftValue = {
      status: 'DONE',
      actualStartDate: '2026-11-02',
      actualEndDate: '2026-11-04',
      touched: false,
    }
    render(
      <ScheduleItemRow
        item={{ ...ITEM, status: 'DONE' }}
        targetDate="2026-11-05"
        readOnly={false}
        value={done}
        onChange={onChange}
      />,
    )
    const endInput = screen.getByLabelText(t('schedule.columns.actualEndDate'))
    expect((endInput as HTMLInputElement).disabled).toBe(false)
    await user.clear(endInput)
    expect(onChange).toHaveBeenLastCalledWith({
      status: 'DONE',
      actualStartDate: '2026-11-02',
      actualEndDate: null,
      touched: true,
    })
  })

  it('highlights the actual end date when the range is invalid', () => {
    const invalidRange: ScheduleItemDraftValue = {
      status: 'DONE',
      actualStartDate: '2026-11-05',
      actualEndDate: '2026-11-01',
      touched: true,
    }
    render(
      <ScheduleItemRow
        item={{ ...ITEM, status: 'DONE' }}
        targetDate="2026-11-05"
        readOnly={false}
        value={invalidRange}
        onChange={onChange}
      />,
    )
    expect(screen.getByLabelText(t('schedule.columns.actualEndDate')).className).toContain(
      'border-danger-text',
    )
  })

  it('highlights the actual start date when it is invalid (future date)', () => {
    const invalid: ScheduleItemDraftValue = {
      status: 'IN_PROGRESS',
      actualStartDate: '2026-12-01',
      actualEndDate: null,
      touched: true,
    }
    render(
      <ScheduleItemRow
        item={{ ...ITEM, status: 'IN_PROGRESS' }}
        targetDate="2026-11-05"
        readOnly={false}
        value={invalid}
        onChange={onChange}
      />,
    )
    expect(screen.getByLabelText(t('schedule.columns.actualStartDate')).className).toContain(
      'border-danger-text',
    )
  })
})

describe('ScheduleItemRow（readOnly）', () => {
  it('shows the status label and "no actual" when neither actual date is set', () => {
    render(
      <ScheduleItemRow item={ITEM} targetDate="2026-11-05" readOnly value={VALUE} onChange={onChange} />,
    )
    expect(screen.getByText(t('schedule.status.NOT_STARTED'))).toBeTruthy()
    expect(screen.getByText(t('schedule.gantt.tooltip.noActual'))).toBeTruthy()
  })

  it('shows the actual period when an actual date is set, using the fetched item (not the draft)', () => {
    const doneItem: ScheduleItemForReportRead = {
      ...ITEM,
      status: 'DONE',
      actual_start_date: '2026-11-02',
      actual_end_date: '2026-11-04',
    }
    render(
      <ScheduleItemRow item={doneItem} targetDate="2026-11-05" readOnly value={VALUE} onChange={onChange} />,
    )
    expect(screen.getByText(t('schedule.status.DONE'))).toBeTruthy()
    expect(
      screen.getByText(
        t('schedule.gantt.tooltip.actual', { start: '2026-11-02', end: '2026-11-04' }),
      ),
    ).toBeTruthy()
    // 読み取り専用では下書き（touched=falseのNOT_STARTED）ではなく取得結果を表示する。
    expect(screen.queryByRole('combobox')).toBe(null)
  })

  it('shows an em dash for the missing side when only one actual date is set', () => {
    const inProgressItem: ScheduleItemForReportRead = {
      ...ITEM,
      status: 'IN_PROGRESS',
      actual_start_date: '2026-11-02',
      actual_end_date: null,
    }
    render(
      <ScheduleItemRow item={inProgressItem} targetDate="2026-11-05" readOnly value={VALUE} onChange={onChange} />,
    )
    expect(
      screen.getByText(t('schedule.gantt.tooltip.actual', { start: '2026-11-02', end: '—' })),
    ).toBeTruthy()
  })
})
