import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { QuickRecordFields } from './QuickRecordFields'

const getSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ getSettings }))

beforeEach(() => {
  vi.clearAllMocks()
  getSettings.mockResolvedValue({ quick_record: { voice_hint_dismissed: true } } as AppSettingsRead)
})

afterEach(() => {
  cleanup()
})

describe('QuickRecordFields', () => {
  it('renders the mood picker and note input', () => {
    renderWithProviders(
      <QuickRecordFields
        note=""
        onChangeNote={() => undefined}
        mood={null}
        onChangeMood={() => undefined}
        maxChars={100}
        showNumbersSkippedNotice={false}
      />,
    )

    expect(screen.getByText(t('dailyReport.quickRecord.moodLabel'))).toBeTruthy()
    expect(screen.getByLabelText(t('dailyReport.quickRecord.noteLabel'))).toBeTruthy()
  })

  it('shows the numbers-skipped notice only when asked', () => {
    renderWithProviders(
      <QuickRecordFields
        note=""
        onChangeNote={() => undefined}
        mood={null}
        onChangeMood={() => undefined}
        maxChars={100}
        showNumbersSkippedNotice={true}
      />,
    )

    expect(screen.getByText(t('dailyReport.quickRecord.numbersSkippedNotice'))).toBeTruthy()
  })

  it('calls onChangeNote and onChangeMood from the inner inputs', async () => {
    const user = userEvent.setup()
    const onChangeNote = vi.fn()
    const onChangeMood = vi.fn()
    renderWithProviders(
      <QuickRecordFields
        note=""
        onChangeNote={onChangeNote}
        mood={null}
        onChangeMood={onChangeMood}
        maxChars={100}
        showNumbersSkippedNotice={false}
      />,
    )

    await user.click(screen.getByText(t('dailyReport.quickRecord.moodStamps.4')))
    await user.type(screen.getByLabelText(t('dailyReport.quickRecord.noteLabel')), 'A')

    expect(onChangeMood).toHaveBeenCalledWith(4)
    expect(onChangeNote).toHaveBeenCalledWith('A')
  })
})
