/** 目標相談チャットの判定ロジックのテスト（S09で導入、S10で質問例ボタンのテストを追加、
 * S11で会話の表示名のテストを追加、開発Todo v1.1 F-02・v1.2 F-02）。 */
import { describe, expect, it } from 'vitest'
import {
  conversationDisplayTitle,
  errorMessageKey,
  questionExampleKeys,
  UNAVAILABLE_MESSAGE_KEY,
  validateQuestion,
} from './goalConsultationLogic'

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
    expect(validateQuestion('この後どのような分野の勉強が必要ですか', 300)).toBeNull()
  })
})

describe('UNAVAILABLE_MESSAGE_KEY（表示できない回答の固定文言）', () => {
  it('goalConsultation名前空間のキーを指す', () => {
    expect(UNAVAILABLE_MESSAGE_KEY).toBe('goalConsultation.unavailable')
  })
})

describe('errorMessageKey（通信エラーの文言）', () => {
  it('AI未接続だけを接続案内に分ける', () => {
    expect(errorMessageKey('AI_AUTH_REQUIRED')).toBe('goalConsultation.authRequired')
  })

  it('それ以外のエラー、またはコード不明は汎用の失敗文言', () => {
    expect(errorMessageKey('AI_ERROR')).toBe('goalConsultation.error')
    expect(errorMessageKey(undefined)).toBe('goalConsultation.error')
  })
})

describe('questionExampleKeys（目標の種類ごとの質問例）', () => {
  it('資格は3件のロケールキーを返す', () => {
    expect(questionExampleKeys('EXAM')).toEqual([
      'goalConsultation.questionExamples.exam1',
      'goalConsultation.questionExamples.exam2',
      'goalConsultation.questionExamples.exam3',
    ])
  })

  it('読書は2件のロケールキーを返す', () => {
    expect(questionExampleKeys('READING')).toEqual([
      'goalConsultation.questionExamples.reading1',
      'goalConsultation.questionExamples.reading2',
    ])
  })

  it('仕事は2件のロケールキーを返す', () => {
    expect(questionExampleKeys('WORK')).toEqual([
      'goalConsultation.questionExamples.work1',
      'goalConsultation.questionExamples.work2',
    ])
  })
})

describe('conversationDisplayTitle（会話の表示名、S11）', () => {
  it('タイトルがあればそのまま返す', () => {
    expect(conversationDisplayTitle('科目Aの相談')).toBe('科目Aの相談')
  })

  it('空文字はnullを返す（既定文言は呼び出し側が補う）', () => {
    expect(conversationDisplayTitle('')).toBeNull()
  })

  it('空白だけのタイトルもnullを返す', () => {
    expect(conversationDisplayTitle('   ')).toBeNull()
  })
})
