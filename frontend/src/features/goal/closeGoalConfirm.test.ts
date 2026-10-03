import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { ApiError } from '../../api/client'
import { ERROR_CODES } from '../../constants/errorCodes'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import {
  isCloseConfirmationRequired,
  resolveCloseGoalConfirmView,
  toCloseGoalRequest,
} from './closeGoalConfirm'

describe('resolveCloseGoalConfirmView', () => {
  it('asks the exam goal for a plain confirmation before the server has replied', () => {
    expect(
      resolveCloseGoalConfirmView({ category: 'EXAM', awaitingConfirmWithoutResult: false }),
    ).toEqual({
      mode: 'CONFIRM_ONLY',
      bodyKey: 'goals.detail.closeConfirm.body',
      confirmWithoutResult: false,
    })
  })

  it('switches the exam goal to the without-result wording once confirmation is required', () => {
    expect(
      resolveCloseGoalConfirmView({ category: 'EXAM', awaitingConfirmWithoutResult: true }),
    ).toEqual({
      mode: 'CONFIRM_ONLY',
      bodyKey: 'goals.detail.closeConfirm.withoutResultBody',
      confirmWithoutResult: true,
    })
  })

  it('confirms the reading goal in one step with its own interruption wording', () => {
    // 読書目標に科目・受験結果は存在しないため、資格試験向けの確認文言を出してはならない
    // （2026-09-11の不具合）。承認は1回で足りる（仕様書7.1）。
    expect(
      resolveCloseGoalConfirmView({ category: 'READING', awaitingConfirmWithoutResult: false }),
    ).toEqual({
      mode: 'CONFIRM_ONLY',
      bodyKey: 'goals.detail.closeConfirm.readingBody',
      confirmWithoutResult: true,
    })
  })

  it('keeps the reading goal on one step even if a confirmation flag leaks in', () => {
    // 読書目標では確認待ちを受け取らない想定だが、受け取っても資格試験の文言へ
    // 切り替わらないことを固定する。
    expect(
      resolveCloseGoalConfirmView({ category: 'READING', awaitingConfirmWithoutResult: true }),
    ).toEqual({
      mode: 'CONFIRM_ONLY',
      bodyKey: 'goals.detail.closeConfirm.readingBody',
      confirmWithoutResult: true,
    })
  })

  it('offers the work goal an explicit with/without result choice', () => {
    expect(
      resolveCloseGoalConfirmView({ category: 'WORK', awaitingConfirmWithoutResult: false }),
    ).toEqual({ mode: 'RESULT_CHOICE', bodyKey: 'goals.detail.closeConfirm.workBody' })
  })

  it('resolves every body key to an actual locale entry', () => {
    // t()は未登録キーをキー文字列のまま返すため、キー名の誤りは画面に生キーが出るまで
    // 気付けない。全分岐のキーが実在することをここで固定する。
    for (const category of GOAL_CATEGORIES) {
      for (const awaitingConfirmWithoutResult of [false, true]) {
        const { bodyKey } = resolveCloseGoalConfirmView({ category, awaitingConfirmWithoutResult })
        expect(t(bodyKey), `未登録のロケールキー: ${bodyKey}`).not.toBe(bodyKey)
      }
    }
  })
})

describe('isCloseConfirmationRequired', () => {
  it('treats the confirmation-required code as a confirmation step', () => {
    expect(
      isCloseConfirmationRequired(new ApiError(ERROR_CODES.CLOSE_CONFIRMATION_REQUIRED, '確認が必要')),
    ).toBe(true)
  })

  it('does NOT treat a real state error as a confirmation step', () => {
    // 2026-09-11の不具合の再発検知。両者を同一視すると、クローズ済み目標への再クローズ等で
    // 無関係な確認文言を表示したまま本当のエラーを握り潰す。
    expect(
      isCloseConfirmationRequired(
        new ApiError(ERROR_CODES.INVALID_STATE_TRANSITION, '進行中の目標のみクローズできます'),
      ),
    ).toBe(false)
  })

  it('does not treat other api errors as a confirmation step', () => {
    expect(isCloseConfirmationRequired(new ApiError(ERROR_CODES.RESOURCE_EXCEEDED, '超過'))).toBe(
      false,
    )
  })

  it('does not treat non-api failures as a confirmation step', () => {
    expect(isCloseConfirmationRequired(new Error('boom'))).toBe(false)
    expect(isCloseConfirmationRequired(undefined)).toBe(false)
  })
})

describe('toCloseGoalRequest', () => {
  it('fills the unspecified side with false so with_result is never sent by accident', () => {
    // with_result は仕事目標専用で、資格試験・読書にtrueを送るとサーバが拒否する。
    expect(toCloseGoalRequest({ confirmWithoutResult: true })).toEqual({
      confirm_without_result: true,
      with_result: false,
    })
  })

  it('sends with_result for the work goal without confirming anything', () => {
    expect(toCloseGoalRequest({ withResult: true })).toEqual({
      confirm_without_result: false,
      with_result: true,
    })
  })
})

describe('ERROR_CODES', () => {
  it('has a locale entry for every code the app branches on', () => {
    // 未登録コードは errors.default（既定文言）へ黙って落ちるため、綴りのずれは
    // 実行時例外にも型エラーにもならない。
    for (const code of Object.values(ERROR_CODES)) {
      const key = `errors.${code}`
      expect(t(key), `未登録のエラーコード文言: ${key}`).not.toBe(key)
    }
  })
})
