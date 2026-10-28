/** 新規利用者向け1問案内（開発Todo リマインド導線 D1〜D4）の表示・送信内容を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ReminderOnboardingPrompt } from './ReminderOnboardingPrompt'

const getSettings = vi.hoisted(() => vi.fn())
const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ getSettings, updateSettings }))

const syncAutostart = vi.hoisted(() => vi.fn())
vi.mock('../../api/desktop', () => ({ syncAutostart }))

function makeSettings() {
  return {
    desktop: {
      open_browser_on_startup: true,
      launch_at_login: false,
      notification_enabled: true,
      notification_time: '21:00',
      reminder_onboarding_shown: false,
      autostart_banner_dismissed: false,
    },
  }
}

const timeInput = () => screen.getByLabelText(t('desktop.onboardingPrompt.timeLabel')) as HTMLInputElement
const acceptButton = () => screen.getByRole('button', { name: t('desktop.onboardingPrompt.accept') })
const declineButton = () => screen.getByRole('button', { name: t('desktop.onboardingPrompt.decline') })

beforeEach(() => {
  vi.clearAllMocks()
  getSettings.mockResolvedValue(makeSettings())
  updateSettings.mockResolvedValue(undefined)
  syncAutostart.mockResolvedValue({ launch_at_login: true, supported: true, applied: true })
})

afterEach(() => {
  cleanup()
})

describe('ReminderOnboardingPrompt の表示', () => {
  it('shows nothing when open is false', () => {
    renderWithProviders(<ReminderOnboardingPrompt open={false} />)
    expect(screen.queryByText(t('desktop.onboardingPrompt.title'))).toBeNull()
  })

  it('shows the question with the current notification time as the default', async () => {
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)

    expect(screen.getByText(t('desktop.onboardingPrompt.title'))).toBeTruthy()
    await waitFor(() => expect(timeInput().value).toBe('21:00'))
  })
})

describe('ReminderOnboardingPrompt の「受け取る」', () => {
  it('turns on notifications, the chosen time, and autostart, then syncs the registry', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.clear(timeInput())
    await user.type(timeInput(), '07:30')
    await user.click(acceptButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: {
          notification_enabled: true,
          notification_time: '07:30',
          launch_at_login: true,
          reminder_onboarding_shown: true,
        },
      }),
    )
    expect(syncAutostart).toHaveBeenCalled()
  })

  it('disables accept while the chosen time is invalid', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.clear(timeInput())
    expect(acceptButton()).toHaveProperty('disabled', true)
  })
})

describe('ReminderOnboardingPrompt の「受け取らない」', () => {
  it('marks the prompt as shown without touching other desktop settings', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.click(declineButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: { reminder_onboarding_shown: true },
      }),
    )
    expect(syncAutostart).not.toHaveBeenCalled()
  })

  it('treats closing the modal (×) the same as declining', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.click(screen.getByLabelText('close'))

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: { reminder_onboarding_shown: true },
      }),
    )
  })
})

describe('ReminderOnboardingPrompt の自動起動反映結果', () => {
  it('shows an info message when running from source (unsupported)', async () => {
    syncAutostart.mockResolvedValue({ launch_at_login: true, supported: false, applied: false })
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.click(acceptButton())

    await waitFor(() =>
      expect(screen.getByText(t('desktop.autostartSync.unsupported'))).toBeTruthy(),
    )
  })

  it('shows an error message when the registry write failed', async () => {
    syncAutostart.mockResolvedValue({ launch_at_login: true, supported: true, applied: false })
    const user = userEvent.setup()
    renderWithProviders(<ReminderOnboardingPrompt open={true} />)
    await waitFor(() => expect(timeInput().value).toBe('21:00'))

    await user.click(acceptButton())

    await waitFor(() => expect(screen.getByText(t('desktop.autostartSync.failed'))).toBeTruthy())
  })
})
