import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { RecapThemeEntriesCard } from './RecapThemeEntriesCard'

describe('RecapThemeEntriesCard', () => {
  it('shows the empty message when no report is linked', () => {
    render(<RecapThemeEntriesCard entries={[]} />)

    expect(screen.getByText(t('recapTheme.entriesEmpty'))).toBeDefined()
  })

  it('lists each report with its date, source kind and text', () => {
    render(
      <RecapThemeEntriesCard
        entries={[
          { source_kind: 'DIARY', record_date: '2026-03-09', text: 'SMTPの役割' },
          { source_kind: 'READING', record_date: '2026-03-10', text: 'IPの層' },
        ]}
      />,
    )

    expect(screen.getByText('SMTPの役割')).toBeDefined()
    expect(screen.getByText('IPの層')).toBeDefined()
    expect(screen.getByText(`2026-03-10 · ${t('recapTheme.sourceKind.READING')}`)).toBeDefined()
  })
})
