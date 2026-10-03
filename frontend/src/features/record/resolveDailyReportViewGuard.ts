import type { DailyRecordRead } from '../../api/records'
import { isAnyLoading, type QueryLike } from '../../utils/queryGuard'

/** 判定に関与する取得。5本すべての完了を待つが、エラー扱いするのはrecordのみ（下記参照）。 */
export type DailyReportViewGuardQueries = {
  record: QueryLike<DailyRecordRead>
  quota: QueryLike<unknown>
  readingBooks: QueryLike<unknown>
  workAssignments: QueryLike<unknown>
  goals: QueryLike<unknown>
}

/** 日次報告閲覧画面が取るべき表示状態。
 * `READY`は取得済みの記録を同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type DailyReportViewGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'READY'; record: DailyRecordRead }

/**
 * SC-08 日次報告閲覧（DailyReportViewPage）の表示状態を決める純粋関数。
 *
 * ローディング判定とエラー判定が画面の早期returnとして並記されており、取得を1本足すたびに
 * 羅列を直す必要があった。判定を1箇所へ集約し、分岐を純粋関数として検証できるようにする
 * （CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」）。
 *
 * この画面は「待つ取得」と「エラー扱いする取得」が一致しない。記録以外の4本は実績に表示名を
 * 与えるためだけに使い（教材名・書籍名・案件名・目標タブ）、取得できなくても`?? []`として
 * 扱えば記録そのものは読める。一方で取得中に描画すると表示名が後から差し替わるため、完了は
 * 待つ。この非対称は意図的なものであり、一律化すると振る舞いが変わる。
 *
 * @param queries 判定に関与する5本の取得結果
 */
export function resolveDailyReportViewGuard(
  queries: DailyReportViewGuardQueries,
): DailyReportViewGuard {
  const { record, quota, readingBooks, workAssignments, goals } = queries

  if (isAnyLoading([record, quota, readingBooks, workAssignments, goals])) {
    return { kind: 'LOADING' }
  }

  // 表示できないのは記録そのものを読めなかった場合のみ。
  if (record.isError || record.data === undefined) {
    return { kind: 'ERROR', error: record.error }
  }

  return { kind: 'READY', record: record.data }
}
