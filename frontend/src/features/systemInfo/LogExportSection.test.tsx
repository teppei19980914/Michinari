/** SC-15 診断ログのエクスポート（Phase40 診断ログ出力・トレース強化）。
 *
 * プリセットが正しい日付範囲をセットすること、ダウンロードボタンが選択中の期間で
 * APIを呼びブラウザへ保存させることを固定する。「今日」はサーバの論理日
 * （GET /records/today）を起点にする（CLAUDE.md「クライアント側での論理日の判断」禁止）
 * ため、getTodayをスタブして固定した日付で検証する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { LogExportSection } from './LogExportSection'

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../../api/records', () => ({ getToday }))

const downloadLogExport = vi.hoisted(() => vi.fn())
vi.mock('../../api/systemLogs', () => ({ downloadLogExport }))

const downloadBlob = vi.hoisted(() => vi.fn())
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob }))

const TODAY = '2026-09-25'

const downloadButton = () =>
  screen.getByRole('button', { name: t('systemInfo.logExport.downloadButton') })
const presetButton = (key: 'today' | 'last3Days' | 'last7Days') =>
  screen.getByRole('button', { name: t(`systemInfo.logExport.presets.${key}`) })
const fromInput = () => screen.getByLabelText(t('systemInfo.logExport.fromLabel'))
const toInput = () => screen.getByLabelText(t('systemInfo.logExport.toLabel'))

async function renderReady() {
  const result = renderWithProviders(<LogExportSection />)
  await waitFor(() => expect((fromInput() as HTMLInputElement).value).toBe(TODAY))
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  getToday.mockResolvedValue({ logical_date: TODAY, record_state: null })
  downloadLogExport.mockResolvedValue(new Blob(['log content']))
})

afterEach(() => {
  cleanup()
})

describe('LogExportSection の初期状態', () => {
  it('defaults the date range to the server logical date', async () => {
    await renderReady()

    expect((fromInput() as HTMLInputElement).value).toBe(TODAY)
    expect((toInput() as HTMLInputElement).value).toBe(TODAY)
  })

  it('shows a loading message while the logical date has not arrived yet', () => {
    getToday.mockReturnValue(new Promise(() => undefined))

    renderWithProviders(<LogExportSection />)

    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })

  it('shows an error message when the logical date fails to load', async () => {
    getToday.mockRejectedValue(new Error('network down'))

    renderWithProviders(<LogExportSection />)

    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })
})

describe('LogExportSection のプリセット', () => {
  it('sets the range to the last 3 days including today', async () => {
    const user = userEvent.setup()
    await renderReady()

    await user.click(presetButton('last3Days'))

    expect((fromInput() as HTMLInputElement).value).toBe('2026-09-23')
    expect((toInput() as HTMLInputElement).value).toBe(TODAY)
  })

  it('sets the range to the last 7 days including today', async () => {
    const user = userEvent.setup()
    await renderReady()

    await user.click(presetButton('last7Days'))

    expect((fromInput() as HTMLInputElement).value).toBe('2026-09-19')
    expect((toInput() as HTMLInputElement).value).toBe(TODAY)
  })
})

describe('LogExportSection の手動入力', () => {
  it('lets the user override the from/to dates directly', async () => {
    await renderReady()

    fireEvent.change(fromInput(), { target: { value: '2026-09-01' } })
    fireEvent.change(toInput(), { target: { value: '2026-09-10' } })

    expect((fromInput() as HTMLInputElement).value).toBe('2026-09-01')
    expect((toInput() as HTMLInputElement).value).toBe('2026-09-10')
  })
})

describe('LogExportSection のダウンロード', () => {
  it('downloads the log for the currently selected range', async () => {
    const user = userEvent.setup()
    await renderReady()

    await user.click(downloadButton())

    await waitFor(() => expect(downloadLogExport).toHaveBeenCalledWith(TODAY, TODAY))
    expect(downloadBlob.mock.calls[0][1]).toBe(`michinari-logs_${TODAY}_${TODAY}.log`)
  })
})
