/** 1年前の今日の設定（開発Todo_1年前の今日_v1.0 §0 V13）の表示と送信内容を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { OnThisDaySettingsSection } from './OnThisDaySettingsSection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeOnThisDay(
  overrides: Partial<AppSettingsRead['on_this_day']> = {},
): AppSettingsRead['on_this_day'] {
  return {
    enabled: true,
    candidate_months_ago: '1,6,12',
    show_probability: 0.3,
    body_preview_chars: 100,
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['on_this_day']> = {}) {
  return renderWithProviders(
    <OnThisDaySettingsSection
      settings={{ on_this_day: makeOnThisDay(overrides) } as AppSettingsRead}
    />,
  )
}

const enabledCheckbox = () =>
  screen.getByLabelText(t('settings.onThisDay.enabledLabel')) as HTMLInputElement
const candidateInput = () =>
  screen.getByLabelText(t('settings.onThisDay.candidateMonthsAgoLabel')) as HTMLInputElement
const probabilityInput = () =>
  screen.getByLabelText(t('settings.onThisDay.showProbabilityLabel')) as HTMLInputElement
const previewCharsInput = () =>
  screen.getByLabelText(t('settings.onThisDay.bodyPreviewCharsLabel')) as HTMLInputElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('OnThisDaySettingsSection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.onThisDay.title'))).toBeTruthy()
  })

  it('reflects the stored values', () => {
    renderSection({ candidate_months_ago: '3,9' })
    expect(enabledCheckbox().checked).toBe(true)
    expect(candidateInput().value).toBe('3,9')
  })
})

describe('OnThisDaySettingsSection の保存', () => {
  it('sends every field under the on_this_day group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        on_this_day: {
          enabled: true,
          candidate_months_ago: '1,6,12',
          show_probability: 0.3,
          body_preview_chars: 100,
        },
      }),
    )
  })

  it('sends an edited field rather than the initial value', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(candidateInput())
    await user.type(candidateInput(), '3,9')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          on_this_day: expect.objectContaining({ candidate_months_ago: '3,9' }),
        }),
      ),
    )
  })

  it('reports success after saving', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })

  it('unchecking enabled still allows saving', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(enabledCheckbox())
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ on_this_day: expect.objectContaining({ enabled: false }) }),
      ),
    )
  })

  it('blocks saving while candidateMonthsAgo is not a valid comma-separated list', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(candidateInput())
    await user.type(candidateInput(), '1,,6')

    expect(screen.getByText(t('settings.onThisDay.candidateMonthsAgoInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    await user.click(saveButton())
    await act(async () => {
      await Promise.resolve()
    })
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('blocks saving while showProbability is out of range', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(probabilityInput())
    await user.type(probabilityInput(), '1.5')

    expect(screen.getByText(t('settings.onThisDay.showProbabilityInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
  })

  it('blocks saving while bodyPreviewChars is not a positive integer', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(previewCharsInput())
    await user.type(previewCharsInput(), '0')

    expect(screen.getByText(t('settings.onThisDay.bodyPreviewCharsInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
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
