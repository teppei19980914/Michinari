/** ヘルプAIアシスタントの判定ロジックのテスト（Phase43、開発Todo F-02）。 */
import { describe, expect, it } from 'vitest'
import { errorMessageKey, FIXED_STATUS_MESSAGE_KEYS, validateQuestion } from './helpAssistantLogic'

describe('validateQuestion（送信前の質問検証）', () => {
  it('空白だけの質問は空として扱う', () => {
    expect(validateQuestion('   \n ', 300)).toBe('empty')
  })

  it('上限ちょうどの質問は通す', () => {
    expect(validateQuestion('あ'.repeat(300), 300)).toBeNull()
  })

  it('上限を超える質問は長すぎるとして扱う（前後の空白は数えない）', () => {
    expect(validateQuestion(`  ${'あ'.repeat(301)}  `, 300)).toBe('tooLong')
  })

  it('通常の質問は問題なし', () => {
    expect(validateQuestion('目標は何種類ありますか', 300)).toBeNull()
  })
})

describe('固定文言のキー（記載なし・表示できない回答）', () => {
  it('記載なしと表示不可で、別々の文言を指す', () => {
    expect(FIXED_STATUS_MESSAGE_KEYS.NOT_FOUND).toBe('helpAssistant.notFound')
    expect(FIXED_STATUS_MESSAGE_KEYS.UNAVAILABLE).toBe('helpAssistant.unavailable')
  })
})

describe('errorMessageKey（通信エラーの文言）', () => {
  it('AI未接続だけを接続案内に分ける', () => {
    expect(errorMessageKey('AI_AUTH_REQUIRED')).toBe('helpAssistant.authRequired')
  })

  it('それ以外のエラー、またはコード不明は汎用の失敗文言', () => {
    expect(errorMessageKey('AI_ERROR')).toBe('helpAssistant.error')
    expect(errorMessageKey(undefined)).toBe('helpAssistant.error')
  })
})
