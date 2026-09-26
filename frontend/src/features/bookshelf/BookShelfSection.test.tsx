import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { makeBook, makeGoal } from '../../test/fixtures'
import type { CompletedReadingBook } from '../../api/goals'
import { BookShelfSection } from './BookShelfSection'

function makeEntry(id: number, title: string): CompletedReadingBook {
  return {
    goal: makeGoal({ id, status: 'CLOSED_WITH_RESULT', archived_at: null }),
    book: makeBook({ id, goal_id: id, title }),
  }
}

afterEach(() => {
  cleanup()
})

describe('BookShelfSection', () => {
  it('renders nothing when there are no entries', () => {
    const { container } = renderWithProviders(
      <BookShelfSection
        titleKey="bookshelf.shelf.completedTitle"
        entries={[]}
        resolveVariant={() => 'completed'}
        onArchive={vi.fn()}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    expect(container.textContent).toBe('')
  })

  it('renders the section title and one card per entry', () => {
    const entries = [makeEntry(1, '本A'), makeEntry(2, '本B')]
    renderWithProviders(
      <BookShelfSection
        titleKey="bookshelf.shelf.completedTitle"
        entries={entries}
        resolveVariant={() => 'completed'}
        onArchive={vi.fn()}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    expect(screen.getByText(t('bookshelf.shelf.completedTitle'))).toBeDefined()
    expect(screen.getByText('本A')).toBeDefined()
    expect(screen.getByText('本B')).toBeDefined()
  })
})
