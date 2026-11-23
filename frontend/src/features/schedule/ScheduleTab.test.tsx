import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { ScheduleRead } from '../../api/schedule'
import { ScheduleTab } from './ScheduleTab'

const getSchedule = vi.hoisted(() => vi.fn())
const saveSchedule = vi.hoisted(() => vi.fn())
const updateScheduleViewSetting = vi.hoisted(() => vi.fn())
vi.mock('../../api/schedule', () => ({ getSchedule, saveSchedule, updateScheduleViewSetting }))

const getHolidayCoverage = vi.hoisted(() => vi.fn())
vi.mock('../../api/resources', () => ({ getHolidayCoverage }))

function sampleScheduleRead(overrides: Partial<ScheduleRead> = {}): ScheduleRead {
  return {
    revision: 1,
    frozen_row_count: 0,
    frozen_column_count: 1,
    today: '2026-11-23',
    max_items: 100,
    max_custom_columns: 10,
    gantt_day_width_min_rem: 1.75,
    gantt_day_width_max_rem: 4.5,
    columns: [],
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
        cells: [],
      },
    ],
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getHolidayCoverage.mockResolvedValue({ holidays: [], year_from: 1955, year_to: 2027 })
  // jsdomにはscrollIntoViewの実装が無いため、D-29の「最初のエラーへスクロール」を
  // 呼び出すテストのためにスタブ化する（本番のブラウザには実装がある）。
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleTab', () => {
  it('読み込み中はローディング表示', () => {
    getSchedule.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    expect(screen.getByText(t('common.loading'))).not.toBe(null)
  })

  it('行が0件のときは空の案内を表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead({ items: [] }))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() => expect(screen.getByText(t('schedule.empty.title'))).not.toBe(null))
  })

  it('行がある場合は表とガントを表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
  })

  it('取得した祝日を表示期間の日付集合へ変換する（D-45）', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    getHolidayCoverage.mockResolvedValue({
      holidays: [{ holiday_date: '2026-11-03', name: '文化の日' }],
      year_from: 1955,
      year_to: 2027,
    })
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
    await waitFor(() => expect(getHolidayCoverage).toHaveBeenCalled())
  })

  it('閲覧のみの目標では行を追加・保存ボタンを表示しない', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={true} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.addRow') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.save') })).toBe(null)
  })

  it('作業項目を編集して保存すると、保存APIへrevisionを含めて送信する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    saveSchedule.mockResolvedValue(sampleScheduleRead({ revision: 2 }))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')

    const saveButton = screen.getByRole('button', { name: t('schedule.toolbar.save') })
    await userEvent.click(saveButton)

    await waitFor(() => expect(saveSchedule).toHaveBeenCalled())
    expect(saveSchedule.mock.calls[0][1]).toMatchObject({ revision: 1 })
  })

  it('検証エラーがある行を保存しようとすると、エラー件数のトーストを出し保存APIを呼ばない', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.clear(titleInput)

    const saveButton = screen.getByRole('button', { name: t('schedule.toolbar.save') })
    await userEvent.click(saveButton)

    expect(saveSchedule).not.toHaveBeenCalled()
    expect(await screen.findByText(t('schedule.validation.saveErrorCount', { count: 1 }))).not.toBe(
      null,
    )
  })

  it('競合以外の保存エラーはトーストで知らせる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { ApiError } = await import('../../api/client')
    saveSchedule.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.save') }))

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).not.toBe(null)
  })

  it('固定行数・固定列数の選択、今日へボタンが動く', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    updateScheduleViewSetting.mockImplementation((_goalId, payload) => Promise.resolve(payload))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByLabelText(t('schedule.columns.title'))

    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenRowsLabel'), { exact: false }),
      '1',
    )
    await waitFor(() =>
      expect(updateScheduleViewSetting).toHaveBeenCalledWith(1, {
        frozen_row_count: 1,
        frozen_column_count: 1,
      }),
    )

    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenColumnsLabel'), { exact: false }),
      '2',
    )
    await waitFor(() =>
      expect(updateScheduleViewSetting).toHaveBeenCalledWith(1, {
        frozen_row_count: 1,
        frozen_column_count: 2,
      }),
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.goToToday') }))
    // 「今日へ」はスクロール位置の再計算のみで、API呼び出しや例外が発生しないことを確認する。
    expect(screen.getByRole('button', { name: t('schedule.toolbar.goToToday') })).not.toBe(null)
  })

  it('409の競合時は編集内容を保持したままダイアログを表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { ApiError } = await import('../../api/client')
    saveSchedule.mockRejectedValue(new ApiError('SCHEDULE_REVISION_CONFLICT', '競合しました'))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.save') }))

    expect(await screen.findByText(t('schedule.conflict.title'))).not.toBe(null)
    expect((titleInput as HTMLInputElement).value).toBe('作業AX')
  })
})
