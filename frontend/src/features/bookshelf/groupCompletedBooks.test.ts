import { describe, expect, it } from 'vitest'
import { makeBook, makeGoal } from '../../test/fixtures'
import type { CompletedReadingBook } from '../../api/goals'
import { groupCompletedBooks } from './groupCompletedBooks'

function makeEntry(overrides: {
  id: number
  status: 'CLOSED_WITH_RESULT' | 'CLOSED_WITHOUT_RESULT'
  archivedAt: string | null
  closedAt: string | null
}): CompletedReadingBook {
  return {
    goal: makeGoal({
      id: overrides.id,
      category: 'READING',
      status: overrides.status,
      archived_at: overrides.archivedAt,
      closed_at: overrides.closedAt,
    }),
    book: makeBook({ goal_id: overrides.id }),
  }
}

describe('groupCompletedBooks', () => {
  it('returns empty buckets for no entries', () => {
    expect(groupCompletedBooks([])).toEqual({
      onShelf: { completed: [], interrupted: [] },
      archived: { completed: [], interrupted: [] },
    })
  })

  it('splits by status (completed/interrupted) and archived_at (onShelf/archived)', () => {
    const onShelfCompleted = makeEntry({
      id: 1,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-01T00:00:00',
    })
    const onShelfInterrupted = makeEntry({
      id: 2,
      status: 'CLOSED_WITHOUT_RESULT',
      archivedAt: null,
      closedAt: '2026-09-02T00:00:00',
    })
    const archivedCompleted = makeEntry({
      id: 3,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: '2026-09-05T00:00:00',
      closedAt: '2026-09-03T00:00:00',
    })
    const archivedInterrupted = makeEntry({
      id: 4,
      status: 'CLOSED_WITHOUT_RESULT',
      archivedAt: '2026-09-06T00:00:00',
      closedAt: '2026-09-04T00:00:00',
    })

    const result = groupCompletedBooks([
      onShelfCompleted,
      onShelfInterrupted,
      archivedCompleted,
      archivedInterrupted,
    ])

    expect(result.onShelf.completed).toEqual([onShelfCompleted])
    expect(result.onShelf.interrupted).toEqual([onShelfInterrupted])
    expect(result.archived.completed).toEqual([archivedCompleted])
    expect(result.archived.interrupted).toEqual([archivedInterrupted])
  })

  it('sorts each bucket by closed_at descending', () => {
    const older = makeEntry({
      id: 1,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-01T00:00:00',
    })
    const newer = makeEntry({
      id: 2,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-10T00:00:00',
    })

    const result = groupCompletedBooks([older, newer])

    expect(result.onShelf.completed).toEqual([newer, older])
  })

  it('breaks a closed_at tie by the larger goal id first', () => {
    const lowerId = makeEntry({
      id: 1,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-01T00:00:00',
    })
    const higherId = makeEntry({
      id: 2,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-01T00:00:00',
    })

    const result = groupCompletedBooks([lowerId, higherId])

    expect(result.onShelf.completed).toEqual([higherId, lowerId])
  })

  it('treats a missing closed_at as sorting last, falling back to the id tiebreak', () => {
    const withoutClosedAt = makeEntry({
      id: 1,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: null,
    })
    const withClosedAt = makeEntry({
      id: 2,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: '2026-09-01T00:00:00',
    })

    const result = groupCompletedBooks([withoutClosedAt, withClosedAt])

    expect(result.onShelf.completed).toEqual([withClosedAt, withoutClosedAt])
  })

  it('falls back to the id tiebreak when both entries have no closed_at', () => {
    const lowerId = makeEntry({
      id: 1,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: null,
    })
    const higherId = makeEntry({
      id: 2,
      status: 'CLOSED_WITH_RESULT',
      archivedAt: null,
      closedAt: null,
    })

    const result = groupCompletedBooks([lowerId, higherId])

    expect(result.onShelf.completed).toEqual([higherId, lowerId])
  })
})
