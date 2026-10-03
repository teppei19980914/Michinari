/** 本棚（SC-18）の振る舞いを固定する。読了棚・中断棚・しまった本の出し分けと、
 * アーカイブ/復元/完全削除の結線を確かめる（GoalsListPage.test.tsxと同じ方針）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeBook, makeGoal } from '../test/fixtures'
import type { CompletedReadingBook } from '../api/goals'
import { BookshelfPage } from './BookshelfPage'

const listCompletedReadingBooks = vi.hoisted(() => vi.fn())
const archiveGoal = vi.hoisted(() => vi.fn())
const unarchiveGoal = vi.hoisted(() => vi.fn())
const deleteArchivedGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({
  listCompletedReadingBooks,
  archiveGoal,
  unarchiveGoal,
  deleteArchivedGoal,
}))

const INTERRUPTED_ID = GOAL_ID + 1
const ARCHIVED_ID = GOAL_ID + 2

function completedEntry(overrides: Parameters<typeof makeGoal>[0] = {}): CompletedReadingBook {
  return {
    goal: makeGoal({ status: 'CLOSED_WITH_RESULT', archived_at: null, ...overrides }),
    book: makeBook({ title: '銀河鉄道の夜' }),
  }
}

const interruptedEntry = (): CompletedReadingBook => ({
  goal: makeGoal({ id: INTERRUPTED_ID, status: 'CLOSED_WITHOUT_RESULT', archived_at: null }),
  book: makeBook({ id: INTERRUPTED_ID, goal_id: INTERRUPTED_ID, title: '吾輩は猫である' }),
})

const archivedEntry = (): CompletedReadingBook => ({
  goal: makeGoal({
    id: ARCHIVED_ID,
    status: 'CLOSED_WITH_RESULT',
    archived_at: '2026-09-10T00:00:00',
  }),
  book: makeBook({ id: ARCHIVED_ID, goal_id: ARCHIVED_ID, title: '坊っちゃん' }),
})

const showArchivedToggle = () =>
  screen.getByRole('checkbox', { name: t('bookshelf.showArchivedToggle') })

beforeEach(() => {
  vi.clearAllMocks()
  listCompletedReadingBooks.mockResolvedValue([])
  archiveGoal.mockResolvedValue(undefined)
  unarchiveGoal.mockResolvedValue(undefined)
  deleteArchivedGoal.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('BookshelfPage の一覧', () => {
  it('shows the empty message when there is no book at all', async () => {
    renderWithProviders(<BookshelfPage />)

    expect(await screen.findByText(t('bookshelf.empty'))).toBeDefined()
  })

  it('shows the completed shelf but not the interrupted shelf title when only completed books exist', async () => {
    listCompletedReadingBooks.mockResolvedValue([completedEntry()])
    renderWithProviders(<BookshelfPage />)

    expect(await screen.findByText(t('bookshelf.shelf.completedTitle'))).toBeDefined()
    expect(screen.getByText('銀河鉄道の夜')).toBeDefined()
    expect(screen.queryByText(t('bookshelf.shelf.interruptedTitle'))).toBeNull()
  })

  it('shows the interrupted shelf separately from the completed shelf', async () => {
    listCompletedReadingBooks.mockResolvedValue([completedEntry(), interruptedEntry()])
    renderWithProviders(<BookshelfPage />)

    expect(await screen.findByText(t('bookshelf.shelf.interruptedTitle'))).toBeDefined()
    expect(screen.getByText('吾輩は猫である')).toBeDefined()
  })

  it('hides the archive toggle when nothing is archived', async () => {
    listCompletedReadingBooks.mockResolvedValue([completedEntry()])
    renderWithProviders(<BookshelfPage />)

    await screen.findByText('銀河鉄道の夜')
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('keeps archived books out of the shelves until the toggle is switched on', async () => {
    const user = userEvent.setup()
    listCompletedReadingBooks.mockResolvedValue([completedEntry(), archivedEntry()])
    renderWithProviders(<BookshelfPage />)

    await screen.findByText('銀河鉄道の夜')
    expect(screen.queryByText('坊っちゃん')).toBeNull()

    await user.click(showArchivedToggle())

    expect(screen.getByText('坊っちゃん')).toBeDefined()
    expect(screen.getByText(t('bookshelf.archivedSectionTitle'))).toBeDefined()
  })
})

describe('BookshelfPage のアーカイブ操作', () => {
  it('does not archive when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    listCompletedReadingBooks.mockResolvedValue([completedEntry()])
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<BookshelfPage />)

    await user.click(
      await screen.findByRole('button', { name: t('bookshelf.book.archiveButton') }),
    )

    expect(archiveGoal).not.toHaveBeenCalled()
  })

  it('archives after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    listCompletedReadingBooks.mockResolvedValue([completedEntry()])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<BookshelfPage />)

    await user.click(
      await screen.findByRole('button', { name: t('bookshelf.book.archiveButton') }),
    )

    await waitFor(() => expect(archiveGoal).toHaveBeenCalledOnce())
    expect(archiveGoal.mock.calls[0][0]).toBe(GOAL_ID)
  })

  it('restores an archived book without asking for a confirmation', async () => {
    const user = userEvent.setup()
    listCompletedReadingBooks.mockResolvedValue([archivedEntry()])
    renderWithProviders(<BookshelfPage />)

    await user.click(await screen.findByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: t('bookshelf.book.restoreButton') }))

    await waitFor(() => expect(unarchiveGoal).toHaveBeenCalledOnce())
    expect(unarchiveGoal.mock.calls[0][0]).toBe(ARCHIVED_ID)
  })

  it('opens the delete confirmation modal for an archived book and deletes it', async () => {
    const user = userEvent.setup()
    listCompletedReadingBooks.mockResolvedValue([archivedEntry()])
    renderWithProviders(<BookshelfPage />)

    await user.click(await screen.findByRole('checkbox'))
    await user.click(
      screen.getByRole('button', { name: t('bookshelf.book.deleteCompletelyButton') }),
    )

    expect(await screen.findByText(t('goals.list.deleteModal.title'))).toBeDefined()

    await user.click(screen.getByRole('button', { name: t('goals.list.deleteModal.confirmButton') }))

    await waitFor(() => expect(deleteArchivedGoal).toHaveBeenCalledOnce())
    expect(deleteArchivedGoal.mock.calls[0][0]).toBe(ARCHIVED_ID)
  })
})
