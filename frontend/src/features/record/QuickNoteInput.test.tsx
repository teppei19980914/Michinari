import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { QuickNoteInput } from './QuickNoteInput'

afterEach(() => {
  cleanup()
})

describe('QuickNoteInput', () => {
  it('shows the current value and character counter', () => {
    render(<QuickNoteInput value="今日は良い日" onChange={() => undefined} maxChars={100} />)

    expect(screen.getByLabelText(t('dailyReport.quickRecord.noteLabel'))).toHaveProperty(
      'value',
      '今日は良い日',
    )
    expect(
      screen.getByText(t('dailyReport.quickRecord.noteCounter', { current: 6, max: 100 })),
    ).toBeTruthy()
  })

  it('applies maxChars as the input maxLength', () => {
    render(<QuickNoteInput value="" onChange={() => undefined} maxChars={50} />)
    expect(screen.getByLabelText(t('dailyReport.quickRecord.noteLabel'))).toHaveProperty(
      'maxLength',
      50,
    )
  })

  it('calls onChange with the typed text', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<QuickNoteInput value="" onChange={onChange} maxChars={100} />)

    await user.type(screen.getByLabelText(t('dailyReport.quickRecord.noteLabel')), 'A')

    expect(onChange).toHaveBeenCalledWith('A')
  })
})
