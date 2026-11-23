/** 日種別の既定設定・祝日の扱い・祝日の収録範囲表示と手動取込み（開発Todo_スケジュール・
 * ガントチャート_v1.1.md D-46）の送信内容と出し分けを固定する回帰テスト。
 *
 * 収録範囲の有無による文言の出し分け、取込み中のボタン無効化、取込み成功時のトースト・
 * 再取得、失敗時のエラー表示、ファイル未選択時に何もしないことを守る。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ApiError } from '../../api/client'
import type { HolidayListRead } from '../../api/resources'
import { DayTypeDefaultsCard } from './DayTypeDefaultsCard'

const getDayTypeDefaults = vi.hoisted(() => vi.fn())
const updateDayTypeDefaults = vi.hoisted(() => vi.fn())
const getHolidayTreatAsBuffer = vi.hoisted(() => vi.fn())
const updateHolidayTreatAsBuffer = vi.hoisted(() => vi.fn())
const getHolidayCoverage = vi.hoisted(() => vi.fn())
const importHolidaysFile = vi.hoisted(() => vi.fn())
vi.mock('../../api/resources', () => ({
  getDayTypeDefaults,
  updateDayTypeDefaults,
  getHolidayTreatAsBuffer,
  updateHolidayTreatAsBuffer,
  getHolidayCoverage,
  importHolidaysFile,
}))

const importButton = () =>
  screen.getByRole('button', { name: t('resources.dayTypeDefaults.importHolidaysButton') })
const fileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement

function makeCoverage(overrides: Partial<HolidayListRead> = {}): HolidayListRead {
  return { holidays: [], year_from: null, year_to: null, ...overrides }
}

beforeEach(() => {
  getDayTypeDefaults.mockResolvedValue({})
  updateDayTypeDefaults.mockResolvedValue({})
  getHolidayTreatAsBuffer.mockResolvedValue({ treat_as_buffer: true })
  updateHolidayTreatAsBuffer.mockResolvedValue({ treat_as_buffer: false })
  getHolidayCoverage.mockResolvedValue(makeCoverage())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DayTypeDefaultsCard', () => {
  it('曜日ごとの既定値を変更すると該当する曜日だけ送信する', async () => {
    renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    const select = screen.getByLabelText(t('resources.weekdays.0')) as HTMLSelectElement
    await userEvent.selectOptions(select, 'BUFFER')

    await waitFor(() => expect(updateDayTypeDefaults).toHaveBeenCalledWith({ 0: 'BUFFER' }))
  })

  it('祝日を一律で予備日として扱うチェックボックスの変更を送信する', async () => {
    renderWithProviders(<DayTypeDefaultsCard />)
    const checkbox = (await screen.findByRole('checkbox', {
      name: t('resources.dayTypeDefaults.holidayTreatAsBuffer'),
    })) as HTMLInputElement
    expect(checkbox.checked).toBe(true)

    await userEvent.click(checkbox)

    await waitFor(() => expect(updateHolidayTreatAsBuffer).toHaveBeenCalledWith(false))
  })

  it('祝日の設定が未取得の間はチェックボックスを表示しない', async () => {
    getHolidayTreatAsBuffer.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    expect(
      screen.queryByRole('checkbox', {
        name: t('resources.dayTypeDefaults.holidayTreatAsBuffer'),
      }),
    ).toBeNull()
  })

  it('祝日データが未収録の場合はその旨を表示する', async () => {
    renderWithProviders(<DayTypeDefaultsCard />)

    await screen.findByText(t('resources.dayTypeDefaults.holidayCoverageNone'))
  })

  it('祝日データが収録済みの場合は年の範囲を表示する', async () => {
    getHolidayCoverage.mockResolvedValue(makeCoverage({ year_from: 1955, year_to: 2027 }))
    renderWithProviders(<DayTypeDefaultsCard />)

    await screen.findByText(
      t('resources.dayTypeDefaults.holidayCoverageRange', { from: 1955, to: 2027 }),
    )
  })

  it('ファイルを選択すると取込みを実行し、成功したら件数と年範囲をトーストで知らせる', async () => {
    importHolidaysFile.mockResolvedValue({ imported_count: 2, year_from: 2026, year_to: 2026 })
    const { container } = renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    await userEvent.click(importButton())

    const file = new File(['content'], 'holidays.csv', { type: 'text/csv' })
    await userEvent.upload(fileInput(container), file)

    expect(importHolidaysFile).toHaveBeenCalledWith(file)
    await screen.findByText(
      t('resources.dayTypeDefaults.importHolidaysSuccess', { count: 2, from: 2026, to: 2026 }),
    )
    await waitFor(() => expect(getHolidayCoverage).toHaveBeenCalledTimes(2))
  })

  it('取込み中はボタンを押せなくし、完了すると再び押せるようにする', async () => {
    let resolveImport: (value: { imported_count: number; year_from: number; year_to: number }) => void =
      () => {}
    importHolidaysFile.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveImport = resolve
        }),
    )
    const { container } = renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    const file = new File(['content'], 'holidays.csv', { type: 'text/csv' })
    await userEvent.upload(fileInput(container), file)

    await waitFor(() => expect((importButton() as HTMLButtonElement).disabled).toBe(true))

    resolveImport({ imported_count: 1, year_from: 2026, year_to: 2026 })

    await waitFor(() => expect((importButton() as HTMLButtonElement).disabled).toBe(false))
  })

  it('取込みに失敗した場合はエラーをトーストで知らせる', async () => {
    importHolidaysFile.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'CSVが不正です'))
    const { container } = renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    const file = new File(['content'], 'holidays.csv', { type: 'text/csv' })
    await userEvent.upload(fileInput(container), file)

    await screen.findByText(t('errors.VALIDATION_ERROR'))
  })

  it('ファイル選択を取り消した場合は何もしない', async () => {
    const { container } = renderWithProviders(<DayTypeDefaultsCard />)
    await screen.findByText(t('resources.dayTypeDefaults.title'))

    fireEvent.change(fileInput(container), { target: { files: [] } })

    expect(importHolidaysFile).not.toHaveBeenCalled()
  })
})
