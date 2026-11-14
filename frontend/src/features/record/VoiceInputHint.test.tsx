/** 音声入力ヒントの「閉じたら再表示しない」（開発Todo「ひとこと記録」v1.0 Q5・F6）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { VoiceInputHint } from './VoiceInputHint'

const getSettings = vi.hoisted(() => vi.fn())
const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ getSettings, updateSettings }))

function makeSettings(dismissed: boolean): AppSettingsRead {
  return { quick_record: { voice_hint_dismissed: dismissed } } as AppSettingsRead
}

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('VoiceInputHint', () => {
  it('shows the hint when not yet dismissed', async () => {
    getSettings.mockResolvedValue(makeSettings(false))
    renderWithProviders(<VoiceInputHint />)

    expect(await screen.findByText(t('dailyReport.voiceInputHint'))).toBeTruthy()
  })

  it('shows nothing once dismissed', async () => {
    getSettings.mockResolvedValue(makeSettings(true))
    renderWithProviders(<VoiceInputHint />)

    await waitFor(() => expect(getSettings).toHaveBeenCalled())
    expect(screen.queryByText(t('dailyReport.voiceInputHint'))).toBe(null)
  })

  it('persists the dismissal via the quick_record setting', async () => {
    getSettings.mockResolvedValue(makeSettings(false))
    const user = userEvent.setup()
    renderWithProviders(<VoiceInputHint />)

    await user.click(await screen.findByLabelText(t('dailyReport.voiceInputHintDismiss')))

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ quick_record: { voice_hint_dismissed: true } }),
    )
  })
})
