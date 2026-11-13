/** ひとこと記録モードの設定（開発Todo「ひとこと記録」v1.0）の表示と送信内容を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { QuickRecordSettingsSection } from './QuickRecordSettingsSection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeQuickRecord(
  overrides: Partial<AppSettingsRead['quick_record']> = {},
): AppSettingsRead['quick_record'] {
  return {
    note_max_chars: 100,
    last_mode_exam: 'NORMAL',
    last_mode_reading: 'NORMAL',
    last_mode_work: 'NORMAL',
    voice_hint_dismissed: false,
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['quick_record']> = {}) {
  return renderWithProviders(
    <QuickRecordSettingsSection
      settings={{ quick_record: makeQuickRecord(overrides) } as AppSettingsRead}
    />,
  )
}

const noteMaxCharsInput = () =>
  screen.getByLabelText(t('settings.quickRecord.noteMaxCharsLabel')) as HTMLInputElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('QuickRecordSettingsSection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.quickRecord.title'))).toBeTruthy()
  })

  it('reflects the stored value', () => {
    renderSection({ note_max_chars: 50 })
    expect(noteMaxCharsInput().value).toBe('50')
  })
})

describe('QuickRecordSettingsSection の保存', () => {
  it('sends the edited note_max_chars under the quick_record group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(noteMaxCharsInput())
    await user.type(noteMaxCharsInput(), '80')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ quick_record: { note_max_chars: 80 } }),
    )
  })

  it('reports success after saving', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })

  it('blocks saving while note_max_chars is not a positive integer', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(noteMaxCharsInput())
    await user.type(noteMaxCharsInput(), '0')

    expect(screen.getByText(t('settings.quickRecord.noteMaxCharsInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    await user.click(saveButton())
    await act(async () => {
      await Promise.resolve()
    })
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('surfaces a failure instead of reporting success', async () => {
    const user = userEvent.setup()
    updateSettings.mockRejectedValue(new Error('失敗'))
    renderSection()

    await user.click(saveButton())

    await waitFor(() => expect(updateSettings).toHaveBeenCalled())
    expect(screen.queryByText(t('common.saveSucceeded'))).toBe(null)
  })
})
