/** 節目の閾値設定（開発Todo_節目のお祝い_v1.0 F-08b）の表示と送信内容を固定する。
 *
 * 6欄を1つの保存操作でまとめて送る。どれか1つでも送信先のキーを取り違えると、画面上は
 * 同じ形のテキスト欄が並ぶだけで気づけないまま、別の節目種別の閾値が書き換わってしまう。
 * 送信内容まで含めて固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { MilestoneThresholdSection } from './MilestoneThresholdSection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeThreshold(
  overrides: Partial<AppSettingsRead['milestone_threshold']> = {},
): AppSettingsRead['milestone_threshold'] {
  return {
    consecutive_days_thresholds: '3,7,14,30,50,100,200,365',
    total_record_days_thresholds: '10,30,100,365',
    reading_total_pages_thresholds: '500,1000,3000,5000,10000',
    reading_completed_books_thresholds: '1,3,5,10',
    exam_overall_progress_thresholds: '25,50,75',
    work_record_count_thresholds: '10,50,100',
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['milestone_threshold']> = {}) {
  return renderWithProviders(
    <MilestoneThresholdSection
      settings={{ milestone_threshold: makeThreshold(overrides) } as AppSettingsRead}
    />,
  )
}

const consecutiveDaysInput = () =>
  screen.getByLabelText(
    t('settings.milestoneThreshold.consecutiveDaysThresholdsLabel'),
  ) as HTMLInputElement
const workRecordCountInput = () =>
  screen.getByLabelText(
    t('settings.milestoneThreshold.workRecordCountThresholdsLabel'),
  ) as HTMLInputElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('MilestoneThresholdSection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.milestoneThreshold.title'))).toBeTruthy()
  })

  it('reflects the stored values', () => {
    renderSection({ consecutive_days_thresholds: '7,14' })
    expect(consecutiveDaysInput().value).toBe('7,14')
  })
})

describe('MilestoneThresholdSection の保存', () => {
  it('sends every field under the milestone_threshold group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        milestone_threshold: {
          consecutive_days_thresholds: '3,7,14,30,50,100,200,365',
          total_record_days_thresholds: '10,30,100,365',
          reading_total_pages_thresholds: '500,1000,3000,5000,10000',
          reading_completed_books_thresholds: '1,3,5,10',
          exam_overall_progress_thresholds: '25,50,75',
          work_record_count_thresholds: '10,50,100',
        },
      }),
    )
  })

  it('sends an edited field rather than the initial value', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(workRecordCountInput())
    await user.type(workRecordCountInput(), '20,60')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          milestone_threshold: expect.objectContaining({ work_record_count_thresholds: '20,60' }),
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

  it('blocks saving while a field is not a valid comma-separated list', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(workRecordCountInput())
    await user.type(workRecordCountInput(), '10,,50')

    expect(screen.getByText(t('settings.milestoneThreshold.invalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    // 無効なボタンを実際に押しても送信されないことまで確かめる（CODING_RULES.md
    // 「落ちないテストに注意する」）。
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
