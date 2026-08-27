import { describe, expect, it } from 'vitest'
import { filterHelpSections, type HelpSearchEntry } from './helpContent'

const ENTRIES: HelpSearchEntry[] = [
  { id: 'dashboard', title: 'ダッシュボード', body: ['本日のノルマを確認できます。'] },
  { id: 'aiConnection', title: '設定 — AI接続', body: ['Hostはxxx.newton-x.netの形式で入力します。'] },
  { id: 'faq', title: 'よくある質問', body: ['PATはNewtonXのWeb版で発行します。'] },
]

describe('filterHelpSections', () => {
  it('returns all ids when the query is empty', () => {
    expect(filterHelpSections(ENTRIES, '')).toEqual(['dashboard', 'aiConnection', 'faq'])
  })

  it('returns all ids when the query is only whitespace', () => {
    expect(filterHelpSections(ENTRIES, '   ')).toEqual(['dashboard', 'aiConnection', 'faq'])
  })

  it('matches by title', () => {
    expect(filterHelpSections(ENTRIES, 'ダッシュボード')).toEqual(['dashboard'])
  })

  it('matches by body content', () => {
    expect(filterHelpSections(ENTRIES, 'newton-x.net')).toEqual(['aiConnection'])
  })

  it('is case-insensitive', () => {
    expect(filterHelpSections(ENTRIES, 'NEWTON-X')).toEqual(['aiConnection'])
  })

  it('returns an empty array when nothing matches', () => {
    expect(filterHelpSections(ENTRIES, '存在しないキーワード')).toEqual([])
  })
})
