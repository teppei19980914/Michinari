import { describe, expect, it } from 'vitest'
import { patchFormValue } from './formValues'

type Draft = { body: string; minutes: string }

const CURRENT: Record<number, Draft> = {
  1: { body: 'one', minutes: '10' },
  2: { body: 'two', minutes: '20' },
}

describe('patchFormValue', () => {
  it('replaces only the given field of the given id', () => {
    expect(patchFormValue(CURRENT, 1, 'body', 'edited')).toEqual({
      1: { body: 'edited', minutes: '10' },
      2: { body: 'two', minutes: '20' },
    })
  })

  it('keeps the other ids untouched so drafts of other goals are not lost', () => {
    expect(patchFormValue(CURRENT, 1, 'body', 'edited')[2]).toEqual(CURRENT[2])
  })

  it('does not mutate the given draft', () => {
    patchFormValue(CURRENT, 1, 'body', 'edited')
    expect(CURRENT[1]).toEqual({ body: 'one', minutes: '10' })
  })

  it('creates the entry when the id has no value yet', () => {
    expect(patchFormValue<Draft, 'body'>({}, 9, 'body', 'new')).toEqual({ 9: { body: 'new' } })
  })
})
