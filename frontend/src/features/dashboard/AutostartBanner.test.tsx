/** 既存利用者向けダッシュボード案内（開発Todo リマインド導線 D1・D5）の表示・送信内容を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AutostartBanner } from './AutostartBanner'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

const syncAutostart = vi.hoisted(() => vi.fn())
vi.mock('../../api/desktop', () => ({ syncAutostart }))

const enableButton = () =>
  screen.getByRole('button', { name: t('dashboard.autostartBanner.enable') })
const dismissButton = () => screen.getByLabelText(t('dashboard.autostartBanner.dismiss'))

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
  syncAutostart.mockResolvedValue({ launch_at_login: true, supported: true, applied: true })
})

afterEach(() => {
  cleanup()
})

describe('AutostartBanner の表示', () => {
  it('shows nothing when show is false', () => {
    renderWithProviders(<AutostartBanner show={false} />)
    expect(screen.queryByText(t('dashboard.autostartBanner.description'))).toBeNull()
  })

  it('shows the banner when show is true', () => {
    renderWithProviders(<AutostartBanner show={true} />)
    expect(screen.getByText(t('dashboard.autostartBanner.description'))).toBeTruthy()
  })
})

describe('AutostartBanner の「有効にする」', () => {
  it('turns on autostart and syncs the registry', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AutostartBanner show={true} />)

    await user.click(enableButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ desktop: { launch_at_login: true } }),
    )
    expect(syncAutostart).toHaveBeenCalled()
  })

  it('shows an info message when running from source (unsupported)', async () => {
    syncAutostart.mockResolvedValue({ launch_at_login: true, supported: false, applied: false })
    const user = userEvent.setup()
    renderWithProviders(<AutostartBanner show={true} />)

    await user.click(enableButton())

    await waitFor(() =>
      expect(screen.getByText(t('desktop.autostartSync.unsupported'))).toBeTruthy(),
    )
  })

  it('shows an error message when the registry write failed', async () => {
    syncAutostart.mockResolvedValue({ launch_at_login: true, supported: true, applied: false })
    const user = userEvent.setup()
    renderWithProviders(<AutostartBanner show={true} />)

    await user.click(enableButton())

    await waitFor(() => expect(screen.getByText(t('desktop.autostartSync.failed'))).toBeTruthy())
  })
})

describe('AutostartBanner の「閉じる」', () => {
  it('marks the banner as dismissed without touching autostart', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AutostartBanner show={true} />)

    await user.click(dismissButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: { autostart_banner_dismissed: true },
      }),
    )
    expect(syncAutostart).not.toHaveBeenCalled()
  })
})
