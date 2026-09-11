/**
 * 目標クローズ確認モーダル（MD-03）の判定ロジック（仕様書7.1）。
 *
 * CloseGoalModal から判定だけを切り出した純粋関数群。フロントにコンポーネントの描画テスト
 * 基盤（jsdom等）が無いため、分岐はこちらへ寄せて単体テストで網羅する
 * （CODING_RULES.md テストカバレッジ）。残る JSX の出し分けのみがテスト対象外となる。
 *
 * 種別ごとの違いは仕様書7.1の遷移条件に対応する。
 * - 資格試験: 全科目の受験結果が登録済みなら「結果あり」で自動クローズ。未登録が残る場合は
 *   サーバが確認を要求し、確認のうえ再送する（2段階）
 * - 読書: 受験結果の概念が無く自動判定できないため、モーダルの承認そのものを確認とみなして
 *   1回で送る。この操作は「読了」ではなく「中断」であり、読了は書籍タブの
 *   「読了として記録する」（POST /books/{id}/complete）を用いる
 * - 仕事: 結果あり（納品等）／結果なし（中止・打ち切り）を利用者が明示的に選ぶ（要件定義書R-72）
 */
import { ApiError } from '../../api/client'
import type { GoalCategory, GoalCloseRequest } from '../../api/goals'
import { ERROR_CODES } from '../../constants/errorCodes'

/** モーダル下部のボタン構成。 */
export type CloseGoalConfirmView =
  /** 「確定」1つ。押下時に confirmWithoutResult を送る（資格試験・読書）。 */
  | { mode: 'CONFIRM_ONLY'; bodyKey: string; confirmWithoutResult: boolean }
  /** 「結果あり」「結果なし」の2ボタン（仕事目標のみ）。 */
  | { mode: 'RESULT_CHOICE'; bodyKey: string }

/**
 * モーダルの本文と送信値を目標種別から決める。
 *
 * @param category 目標種別。`undefined` を許容しないのは、渡し忘れが静かに資格試験として
 *   扱われる事故を防ぐため（呼び出し側が必ず明示する）
 * @param awaitingConfirmWithoutResult サーバが確認を要求し、「結果なしでよいか」の確認待ちに
 *   入っているか（資格試験でのみ true になり得る）
 * @returns 表示する本文のロケールキーとボタン構成
 *
 * @example
 * resolveCloseGoalConfirmView({ category: 'READING', awaitingConfirmWithoutResult: false })
 * // => { mode: 'CONFIRM_ONLY', bodyKey: 'goals.detail.closeConfirm.readingBody', confirmWithoutResult: true }
 */
export function resolveCloseGoalConfirmView(params: {
  category: GoalCategory
  awaitingConfirmWithoutResult: boolean
}): CloseGoalConfirmView {
  const { category, awaitingConfirmWithoutResult } = params

  if (category === 'WORK') {
    return { mode: 'RESULT_CHOICE', bodyKey: 'goals.detail.closeConfirm.workBody' }
  }

  if (category === 'READING') {
    // 読書目標に未登録の受験結果は存在しないため確認待ちには入らない。モーダルの承認を
    // もって確認済みとして送る（仕様書7.1「確認モーダルでの承認」。承認は1回）。
    return {
      mode: 'CONFIRM_ONLY',
      bodyKey: 'goals.detail.closeConfirm.readingBody',
      confirmWithoutResult: true,
    }
  }

  return {
    mode: 'CONFIRM_ONLY',
    bodyKey: awaitingConfirmWithoutResult
      ? 'goals.detail.closeConfirm.withoutResultBody'
      : 'goals.detail.closeConfirm.body',
    confirmWithoutResult: awaitingConfirmWithoutResult,
  }
}

/**
 * クローズ要求の失敗が「確認待ち」か（＝確認表示へ切り替えてよいか）を判定する。
 *
 * 確認待ち以外のエラー（クローズ済み目標への再クローズ等）で true を返してはならない。
 * かつて両者が同じエラーコードだったため、本当の状態エラーまで「確認が必要」と誤解し、
 * 無関係な確認文言を出したまま本当のエラーを握り潰していた
 * （詳細は backend/app/services/exceptions.py の CloseConfirmationRequiredError を参照）。
 *
 * @param error mutation が受け取った例外（ApiError 以外・非 Error も渡り得る）
 * @returns 確認待ちなら true、それ以外（通信エラー等を含む）は false
 *
 * @example
 * isCloseConfirmationRequired(new ApiError('INVALID_STATE_TRANSITION', '...')) // => false
 */
export function isCloseConfirmationRequired(error: unknown): boolean {
  return error instanceof ApiError && error.code === ERROR_CODES.CLOSE_CONFIRMATION_REQUIRED
}

/**
 * 画面の操作内容を POST /goals/{id}/close のリクエストボディへ変換する。
 *
 * 指定しなかった側を false で明示的に埋める。`with_result` は仕事目標専用で、資格試験・読書に
 * true を送るとサーバが拒否するため（goal_service.close_goal）、既定値の取り違えは
 * そのまま不具合になる。
 *
 * @param payload 押されたボタンに対応する値（片方のみ指定する）
 * @returns サーバへ送るリクエストボディ
 *
 * @example
 * toCloseGoalRequest({ withResult: true }) // => { confirm_without_result: false, with_result: true }
 */
export function toCloseGoalRequest(payload: {
  confirmWithoutResult?: boolean
  withResult?: boolean
}): GoalCloseRequest {
  return {
    confirm_without_result: payload.confirmWithoutResult ?? false,
    with_result: payload.withResult ?? false,
  }
}
