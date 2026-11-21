/** 単語帳の習得の可視化（開発Todo_単語帳_v1.0 要件E E-U8）の設定の表示と送信内容を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { VocabMasterySettingsSection } from './VocabMasterySettingsSection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeVocabMastery(
  overrides: Partial<AppSettingsRead['vocab_mastery']> = {},
): AppSettingsRead['vocab_mastery'] {
  return {
    mastery_streak: 3,
    mastered_terms_thresholds: '10,30,50,100,200,300,500',
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['vocab_mastery']> = {}) {
  return renderWithProviders(
    <VocabMasterySettingsSection
      settings={{ vocab_mastery: makeVocabMastery(overrides) } as AppSettingsRead}
    />,
  )
}

const masteryStreakInput = () =>
  screen.getByLabelText(t('settings.vocabMastery.masteryStreakLabel')) as HTMLInputElement
const thresholdsInput = () =>
  screen.getByLabelText(
    t('settings.vocabMastery.masteredTermsThresholdsLabel'),
  ) as HTMLInputElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('VocabMasterySettingsSection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.vocabMastery.title'))).toBeTruthy()
  })

  it('reflects the stored values', () => {
    renderSection({ mastery_streak: 5, mastered_terms_thresholds: '20,40' })
    expect(masteryStreakInput().value).toBe('5')
    expect(thresholdsInput().value).toBe('20,40')
  })
})

describe('VocabMasterySettingsSection の保存', () => {
  it('sends the edited fields under the vocab_mastery group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(masteryStreakInput())
    await user.type(masteryStreakInput(), '4')
    await user.clear(thresholdsInput())
    await user.type(thresholdsInput(), '10,20')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        vocab_mastery: { mastery_streak: 4, mastered_terms_thresholds: '10,20' },
      }),
    )
  })

  it('reports success after saving', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })

  it('blocks saving while masteryStreak is not a positive integer', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(masteryStreakInput())
    await user.type(masteryStreakInput(), '0')

    expect(screen.getByText(t('settings.vocabMastery.masteryStreakInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    await user.click(saveButton())
    await act(async () => {
      await Promise.resolve()
    })
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('blocks saving while masteredTermsThresholds is malformed', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(thresholdsInput())
    await user.type(thresholdsInput(), '10,abc')

    expect(screen.getByText(t('settings.vocabMastery.thresholdsInvalid'))).toBeTruthy()
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
