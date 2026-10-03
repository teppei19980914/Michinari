import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { PreviousEntryHint } from './PreviousEntryHint'

afterEach(() => {
  cleanup()
})

describe('PreviousEntryHint', () => {
  it('renders nothing when there is no previous entry', () => {
    const { container } = render(<PreviousEntryHint entry={null} />)
    expect(container.firstChild).toBe(null)
  })

  it('renders nothing while the previous entry is still loading (undefined)', () => {
    const { container } = render(<PreviousEntryHint entry={undefined} />)
    expect(container.firstChild).toBe(null)
  })

  it('shows the full body without an expand button when it fits within the preview length', () => {
    render(<PreviousEntryHint entry={{ record_date: '2026-09-16', body: '短い本文' }} />)

    expect(screen.getByText(t('dailyReport.previousEntry.label'))).toBeTruthy()
    expect(screen.getByText('短い本文')).toBeTruthy()
    expect(screen.queryByRole('button')).toBe(null)
  })

  it('truncates a long body and expands it on click', async () => {
    const user = userEvent.setup()
    const body = 'あ'.repeat(150)
    render(<PreviousEntryHint entry={{ record_date: '2026-09-16', body }} />)

    expect(screen.getByText(`${'あ'.repeat(100)}…`)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: t('dailyReport.previousEntry.expand') }))
    expect(screen.getByText(body)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: t('dailyReport.previousEntry.collapse') }))
    expect(screen.getByText(`${'あ'.repeat(100)}…`)).toBeTruthy()
  })
})
