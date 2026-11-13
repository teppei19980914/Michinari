import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { RecordModeToggle } from './RecordModeToggle'

afterEach(() => {
  cleanup()
})

describe('RecordModeToggle', () => {
  it('marks the current mode as pressed', () => {
    render(<RecordModeToggle mode="QUICK" onChange={() => undefined} />)
    const quickButton = screen
      .getByText(t('dailyReport.quickRecord.modeToggle.quick'))
      .closest('button')
    const normalButton = screen
      .getByText(t('dailyReport.quickRecord.modeToggle.normal'))
      .closest('button')
    expect(quickButton?.getAttribute('aria-pressed')).toBe('true')
    expect(normalButton?.getAttribute('aria-pressed')).toBe('false')
  })

  it('calls onChange with the clicked mode', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<RecordModeToggle mode="NORMAL" onChange={onChange} />)

    await user.click(screen.getByText(t('dailyReport.quickRecord.modeToggle.quick')))

    expect(onChange).toHaveBeenCalledWith('QUICK')
  })
})
