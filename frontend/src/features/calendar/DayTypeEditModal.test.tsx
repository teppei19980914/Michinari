/** 日種別変更モーダル（仕様書6.4「日種別変更: 全ての日、カレンダー内で処理」）の送信内容を
 * 固定する（Phase 36）。
 *
 * 日種別は計画日数の数え方を決める値で、取り違えるとその日以降の日次ノルマが静かにずれる。
 * 「上書きを解除する」は設定を消す別のAPIであり、いずれかの種別を送るのと結果が異なる。
 *
 * カレンダー画面の描画テスト（CalendarPage.test.tsx）を置いたことでこの部品も計測対象に
 * 入ったため、押した結果どう送信されるかまでここで固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DayTypeEditModal } from './DayTypeEditModal'

const setDayType = vi.hoisted(() => vi.fn())
const clearDayType = vi.hoisted(() => vi.fn())
vi.mock('../../api/calendar', () => ({ setDayType, clearDayType }))

const TARGET_DATE = '2026-09-13'

const dayTypeButton = (dayType: string) =>
  screen.getByRole('button', { name: t(`calendar.dayType.${dayType}`) })
const clearButton = () =>
  screen.getByRole('button', { name: t('calendar.dayTypeModal.clearOverride') })

const onClose = vi.fn()

function renderModal(targetDate: string | null = TARGET_DATE) {
  return renderWithProviders(<DayTypeEditModal targetDate={targetDate} onClose={onClose} />)
}

beforeEach(() => {
  vi.clearAllMocks()
  setDayType.mockResolvedValue(undefined)
  clearDayType.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('DayTypeEditModal', () => {
  it('stays closed while no date is selected', () => {
    renderModal(null)
    expect(screen.queryByText(t('calendar.dayTypeModal.title'))).toBe(null)
  })

  it('shows which date is being edited', () => {
    renderModal()
    expect(
      screen.getByText(`${t('calendar.dayTypeModal.targetDateLabel')}: ${TARGET_DATE}`),
    ).toBeTruthy()
  })

  it('offers every day type', () => {
    renderModal()
    for (const dayType of ['PLAN', 'BUFFER', 'OFF']) {
      expect(dayTypeButton(dayType)).toBeTruthy()
    }
  })

  it('sends the day type that was pressed, for the selected date', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(dayTypeButton('BUFFER'))

    await waitFor(() => expect(setDayType).toHaveBeenCalledOnce())
    expect(setDayType).toHaveBeenCalledWith(TARGET_DATE, { day_type: 'BUFFER' })
    expect(clearDayType).not.toHaveBeenCalled()
  })

  it('closes once the day type is saved', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(dayTypeButton('OFF'))
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
  })

  it('clears the override through its own endpoint instead of sending a day type', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(clearButton())

    await waitFor(() => expect(clearDayType).toHaveBeenCalledWith(TARGET_DATE))
    expect(setDayType).not.toHaveBeenCalled()
  })

  it('closes once the override is cleared', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(clearButton())
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
  })

  it('keeps the day type buttons pressed-proof while saving', async () => {
    const user = userEvent.setup()
    setDayType.mockReturnValue(new Promise(() => undefined))
    renderModal()
    await user.click(dayTypeButton('PLAN'))

    await waitFor(() =>
      expect((dayTypeButton('BUFFER') as HTMLButtonElement).disabled).toBe(true),
    )
    expect(setDayType).toHaveBeenCalledOnce()
  })

  it('keeps the clear button pressed-proof while clearing', async () => {
    const user = userEvent.setup()
    clearDayType.mockReturnValue(new Promise(() => undefined))
    renderModal()
    await user.click(clearButton())

    await waitFor(() => expect((clearButton() as HTMLButtonElement).disabled).toBe(true))
    expect(clearDayType).toHaveBeenCalledOnce()
  })

  it('reports a failure instead of closing', async () => {
    const user = userEvent.setup()
    setDayType.mockRejectedValue(new Error('boom'))
    renderModal()
    await user.click(dayTypeButton('PLAN'))

    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('reports a failure of clearing instead of closing', async () => {
    const user = userEvent.setup()
    clearDayType.mockRejectedValue(new Error('boom'))
    renderModal()
    await user.click(clearButton())

    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
    expect(onClose).not.toHaveBeenCalled()
  })
})
