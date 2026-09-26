import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { makeBook, makeGoal } from '../../test/fixtures'
import { BookInfoTab } from './BookInfoTab'

afterEach(() => {
  cleanup()
})

describe('BookInfoTab', () => {
  it('shows the title, author, period and total pages', () => {
    const book = makeBook({
      title: '銀河鉄道の夜',
      author: '宮沢賢治',
      total_pages: 250,
      start_date: '2026-08-01',
    })
    const goal = makeGoal({ status: 'CLOSED_WITH_RESULT', closed_at: '2026-08-20T00:00:00' })

    render(<BookInfoTab book={book} goal={goal} />)

    expect(screen.getByText('銀河鉄道の夜')).toBeDefined()
    expect(screen.getByText('宮沢賢治')).toBeDefined()
    expect(screen.getByText('2026-08-01 〜 2026-08-20')).toBeDefined()
    expect(screen.getByText('250')).toBeDefined()
  })

  it('falls back to the target due date when closed_at is unavailable', () => {
    const book = makeBook({ start_date: '2026-08-01', due_date: '2026-09-30' })
    const goal = makeGoal({ status: 'CLOSED_WITH_RESULT', closed_at: null })

    render(<BookInfoTab book={book} goal={goal} />)

    expect(screen.getByText('2026-08-01 〜 2026-09-30')).toBeDefined()
  })

  it('shows the completed badge and no interrupted note for CLOSED_WITH_RESULT', () => {
    const goal = makeGoal({ status: 'CLOSED_WITH_RESULT' })

    render(<BookInfoTab book={makeBook()} goal={goal} />)

    expect(screen.getByText(t('bookshelf.book.status.completed'))).toBeDefined()
    expect(screen.queryByText(t('bookshelf.detail.info.interruptedNote'))).toBeNull()
  })

  it('shows the interrupted badge and a neutral note for CLOSED_WITHOUT_RESULT', () => {
    const goal = makeGoal({ status: 'CLOSED_WITHOUT_RESULT' })

    render(<BookInfoTab book={makeBook()} goal={goal} />)

    expect(screen.getByText(t('bookshelf.book.status.interrupted'))).toBeDefined()
    expect(screen.getByText(t('bookshelf.detail.info.interruptedNote'))).toBeDefined()
  })

  it('shows the progress rate as a rounded percentage when available', () => {
    const book = makeBook({ progress_rate: 0.42 })
    render(<BookInfoTab book={book} goal={makeGoal({ status: 'CLOSED_WITHOUT_RESULT' })} />)

    expect(screen.getByText('42%')).toBeDefined()
  })

  it('hides the progress rate row when it is null', () => {
    const book = makeBook({ progress_rate: null })
    render(<BookInfoTab book={book} goal={makeGoal({ status: 'CLOSED_WITH_RESULT' })} />)

    expect(screen.queryByText(t('bookshelf.detail.info.progressRate'))).toBeNull()
  })
})
