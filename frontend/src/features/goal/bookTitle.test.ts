import { describe, expect, it } from 'vitest'
import { resolveInitialBookTitle } from './bookTitle'

describe('resolveInitialBookTitle', () => {
  it('falls back to the goal name when no book is registered yet', () => {
    expect(resolveInitialBookTitle(undefined, '獺祭ゼロから学ぶTypeScript')).toBe(
      '獺祭ゼロから学ぶTypeScript',
    )
  })

  it('prefers the registered book title over the goal name once a book exists', () => {
    expect(resolveInitialBookTitle('リーダブルコード', '目標名とは別の書名')).toBe(
      'リーダブルコード',
    )
  })
})
