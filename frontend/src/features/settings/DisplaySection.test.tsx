/** 表示設定（仕様書6.11、UIリッチ化Phase2でaccent_color/font_scaleを追加）の表示と送信内容を固定する。
 *
 * 5項目(言語・テーマ・分析粒度・アクセントカラー・フォントサイズ)を1回の保存操作でまとめて
 * 送るため、どれか1つでも送信先のキーを取り違えると画面上は気づけないまま起きる不具合になる。
 * 送信内容まで含めて固定する（DesktopSection.test.tsxと同じ方針）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { DisplaySection } from './DisplaySection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeDisplay(
  overrides: Partial<AppSettingsRead['display']> = {},
): AppSettingsRead['display'] {
  return {
    locale: 'ja',
    theme: 'system',
    default_granularity: 'WEEK',
    accent_color: 'blue',
    font_scale: 'standard',
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['display']> = {}) {
  return renderWithProviders(
    <DisplaySection settings={{ display: makeDisplay(overrides) } as AppSettingsRead} />,
  )
}

// --- 要素アクセサ ---
const localeSelect = () =>
  screen.getByLabelText(t('settings.display.localeLabel')) as HTMLSelectElement
const themeSelect = () =>
  screen.getByLabelText(t('settings.display.themeLabel')) as HTMLSelectElement
const granularitySelect = () =>
  screen.getByLabelText(t('settings.display.defaultGranularityLabel')) as HTMLSelectElement
const accentColorSelect = () =>
  screen.getByLabelText(t('settings.display.accentColorLabel')) as HTMLSelectElement
const fontScaleSelect = () =>
  screen.getByLabelText(t('settings.display.fontScaleLabel')) as HTMLSelectElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('DisplaySection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.display.title'))).toBeTruthy()
  })

  it('reflects the stored accent color and font scale', () => {
    renderSection({ accent_color: 'green', font_scale: 'large' })

    expect(accentColorSelect().value).toBe('green')
    expect(fontScaleSelect().value).toBe('large')
  })

  it('defaults to blue accent and standard font scale', () => {
    renderSection()

    expect(accentColorSelect().value).toBe('blue')
    expect(fontScaleSelect().value).toBe('standard')
  })
})

describe('DisplaySection の保存', () => {
  it('sends every setting under the display group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        display: {
          locale: 'ja',
          theme: 'system',
          default_granularity: 'WEEK',
          accent_color: 'blue',
          font_scale: 'standard',
        },
      }),
    )
  })

  it('sends the toggled accent color and font scale rather than the initial ones', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.selectOptions(accentColorSelect(), 'purple')
    await user.selectOptions(fontScaleSelect(), 'small')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          display: expect.objectContaining({ accent_color: 'purple', font_scale: 'small' }),
        }),
      ),
    )
  })

  it('sends the toggled theme and granularity rather than the initial ones', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.selectOptions(themeSelect(), 'dark')
    await user.selectOptions(granularitySelect(), 'MONTH')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          display: expect.objectContaining({ theme: 'dark', default_granularity: 'MONTH' }),
        }),
      ),
    )
  })

  it('sends the locale selected in the dropdown', async () => {
    // LOCALESは現状"ja"の1択だが（技術選定書の対象が日本語のみのため）、onChangeの
    // 配線自体はlocale以外のセレクトと同じ形で担保する。
    renderSection()

    fireEvent.change(localeSelect(), { target: { value: 'ja' } })
    const user = userEvent.setup()
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ display: expect.objectContaining({ locale: 'ja' }) }),
      ),
    )
  })

  it('leaves the theme untouched when only the accent color changes', async () => {
    const user = userEvent.setup()
    renderSection({ theme: 'dark' })

    await user.selectOptions(accentColorSelect(), 'orange')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          display: expect.objectContaining({ theme: 'dark', accent_color: 'orange' }),
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

  it('surfaces a failure instead of reporting success', async () => {
    const user = userEvent.setup()
    updateSettings.mockRejectedValue(new Error('失敗'))
    renderSection()

    await user.click(saveButton())

    await waitFor(() => expect(updateSettings).toHaveBeenCalled())
    expect(screen.queryByText(t('common.saveSucceeded'))).toBe(null)
  })
})
