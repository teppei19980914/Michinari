import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { MoodStampPicker } from './MoodStampPicker'

afterEach(() => {
  cleanup()
})

describe('MoodStampPicker', () => {
  it('renders all five mood stamps', () => {
    render(<MoodStampPicker value={null} onChange={() => undefined} />)
    for (const moodValue of [1, 2, 3, 4, 5] as const) {
      expect(screen.getByText(t(`dailyReport.quickRecord.moodStamps.${moodValue}`))).toBeTruthy()
    }
  })

  it('marks the selected stamp as pressed', () => {
    render(<MoodStampPicker value={3} onChange={() => undefined} />)
    const button = screen.getByText(t('dailyReport.quickRecord.moodStamps.3')).closest('button')
    expect(button?.getAttribute('aria-pressed')).toBe('true')
  })

  it('calls onChange with the clicked mood value', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MoodStampPicker value={null} onChange={onChange} />)

    await user.click(screen.getByText(t('dailyReport.quickRecord.moodStamps.5')))

    expect(onChange).toHaveBeenCalledWith(5)
  })
})
