import { afterEach, describe, expect, it } from 'vitest'
import { applyBootstrapLocale } from './bootstrapLocale'
import { getLocale, setLocale } from './t'

afterEach(() => {
  setLocale('ja')
  document.documentElement.lang = ''
})

describe('applyBootstrapLocale', () => {
  it('applies a known locale and reflects it on <html lang>', () => {
    applyBootstrapLocale('en')

    expect(getLocale()).toBe('en')
    expect(document.documentElement.lang).toBe('en')
  })

  it('ignores an unknown locale and keeps the default', () => {
    applyBootstrapLocale('fr')

    expect(getLocale()).toBe('ja')
    expect(document.documentElement.lang).toBe('')
  })
})
