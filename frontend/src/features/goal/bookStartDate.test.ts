import { describe, expect, it } from 'vitest'
import { resolveInitialBookStartDate } from './bookStartDate'

describe('resolveInitialBookStartDate', () => {
  it('falls back to the goal start date when no book is registered yet', () => {
    expect(resolveInitialBookStartDate(undefined, '2026-09-01')).toBe('2026-09-01')
  })

  it('prefers the registered book start date over the goal start date once a book exists', () => {
    expect(resolveInitialBookStartDate('2026-10-15', '2026-09-01')).toBe('2026-10-15')
  })
})
