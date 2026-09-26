import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeBook, makeGoal } from '../../test/fixtures'
import type { CompletedReadingBook } from '../../api/goals'
import { BookSpineCard } from './BookSpineCard'

function makeEntry(overrides: Parameters<typeof makeGoal>[0] = {}): CompletedReadingBook {
  return {
    goal: makeGoal({
      status: 'CLOSED_WITH_RESULT',
      archived_at: null,
      ...overrides,
    }),
    book: makeBook({ title: '銀河鉄道の夜', author: '宮沢賢治' }),
  }
}

afterEach(() => {
  cleanup()
})

describe('BookSpineCard', () => {
  it('shows the title, author and links to the book detail screen', () => {
    renderWithProviders(
      <BookSpineCard
        entry={makeEntry()}
        variant="completed"
        onArchive={vi.fn()}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    expect(screen.getByText('銀河鉄道の夜')).toBeDefined()
    expect(screen.getByText('宮沢賢治')).toBeDefined()
    const link = screen.getByText('銀河鉄道の夜').closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe(ROUTES.bookDetail(GOAL_ID))
  })

  it('shows the completed badge for the completed variant', () => {
    renderWithProviders(
      <BookSpineCard
        entry={makeEntry()}
        variant="completed"
        onArchive={vi.fn()}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    expect(screen.getByText(t('bookshelf.book.status.completed'))).toBeDefined()
  })

  it('shows the interrupted badge for the interrupted variant', () => {
    renderWithProviders(
      <BookSpineCard
        entry={makeEntry({ status: 'CLOSED_WITHOUT_RESULT' })}
        variant="interrupted"
        onArchive={vi.fn()}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    expect(screen.getByText(t('bookshelf.book.status.interrupted'))).toBeDefined()
  })

  it('does not archive when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    const onArchive = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(
      <BookSpineCard
        entry={makeEntry()}
        variant="completed"
        onArchive={onArchive}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('bookshelf.book.archiveButton') }))

    expect(onArchive).not.toHaveBeenCalled()
  })

  it('archives after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    const onArchive = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(
      <BookSpineCard
        entry={makeEntry()}
        variant="completed"
        onArchive={onArchive}
        onUnarchive={vi.fn()}
        onRequestDelete={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('bookshelf.book.archiveButton') }))

    expect(onArchive).toHaveBeenCalledWith(GOAL_ID)
  })

  it('offers restore and delete instead of archive once archived', async () => {
    const user = userEvent.setup()
    const onUnarchive = vi.fn()
    const onRequestDelete = vi.fn()
    const entry = makeEntry({ archived_at: '2026-09-10T00:00:00' })
    renderWithProviders(
      <BookSpineCard
        entry={entry}
        variant="completed"
        onArchive={vi.fn()}
        onUnarchive={onUnarchive}
        onRequestDelete={onRequestDelete}
      />,
    )

    expect(screen.queryByRole('button', { name: t('bookshelf.book.archiveButton') })).toBeNull()

    await user.click(screen.getByRole('button', { name: t('bookshelf.book.restoreButton') }))
    expect(onUnarchive).toHaveBeenCalledWith(GOAL_ID)

    await user.click(
      screen.getByRole('button', { name: t('bookshelf.book.deleteCompletelyButton') }),
    )
    expect(onRequestDelete).toHaveBeenCalledWith(entry.goal)
  })
})
