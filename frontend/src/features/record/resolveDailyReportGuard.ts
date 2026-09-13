import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
  type CategoryPresence,
} from './categoryCompletion'
import { isFinalizableDate } from './finalizableDate'

/** useQueryの結果のうち、表示可否の判定に必要な部分だけを表す型。
 * react-queryの`UseQueryResult`と構造的に互換であり、テストからは素のオブジェクトを渡せる。 */
export type QueryLike<T> = {
  isLoading: boolean
  isError: boolean
  error: unknown
  data: T | undefined
}

/** 判定に関与する取得。補助情報（slotNames）は含めない（useDailyReportData参照）。 */
export type DailyReportGuardQueries = {
  record: QueryLike<DailyRecordRead>
  quota: QueryLike<QuotaItemRead[]>
  readingBooks: QueryLike<unknown>
  workAssignments: QueryLike<unknown>
  goals: QueryLike<unknown>
  today: QueryLike<TodayRead>
}

/** 日次報告画面が取るべき表示状態。
 * `EDITABLE`は取得済みのデータを同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type DailyReportGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'REDIRECT_VIEW' }
  | { kind: 'EDITABLE'; record: DailyRecordRead; quota: QuotaItemRead[] }

/**
 * SC-06 日次報告（DailyReportPage）の表示状態を決める純粋関数。
 *
 * 従来はコンポーネント内の早期returnとして、ローディング判定・エラー判定・2種類の転送判定が
 * 4箇所に散らばっており、取得を1本追加するたびに複数の羅列を直す必要があった（追加漏れが
 * 起きやすい）。判定を1箇所へ集約し、分岐を純粋関数として検証できるようにする
 * （CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」）。
 *
 * 2種類の転送（入力可能期間外・全カテゴリ確定済み）は遷移先が同じ閲覧画面のため`REDIRECT_VIEW`
 * へまとめる。どちらの理由で転送されたかは呼び出し側の描画を変えない。
 *
 * @param queries 判定に関与する6本の取得結果
 * @param presence その日そのカテゴリに確定すべき目標があるか（選択中タブではなく目標の有無で
 *   判定する。理由はcategoryCompletion.isAllCategoriesReportedのコメントを参照）
 * @param targetDate 対象日（YYYY-MM-DD）
 */
export function resolveDailyReportGuard(
  queries: DailyReportGuardQueries,
  presence: CategoryPresence,
  targetDate: string,
): DailyReportGuard {
  const { record, quota, readingBooks, workAssignments, goals, today } = queries
  // エラーメッセージの優先順もこの並び順に従う（先に失敗を検出した取得のエラーを表示する）。
  const allQueries = [record, quota, readingBooks, workAssignments, goals, today]

  if (allQueries.some((query) => query.isLoading)) {
    return { kind: 'LOADING' }
  }

  const failed = allQueries.find((query) => query.isError)
  // 取得済みデータの有無まで要求するのはこの4本のみ。readingBooks・workAssignmentsは
  // 以降も`?? []`として扱い、取得できなくても他カテゴリの入力を妨げない（従来の挙動）。
  if (
    failed ||
    record.data === undefined ||
    quota.data === undefined ||
    goals.data === undefined ||
    today.data === undefined
  ) {
    return { kind: 'ERROR', error: failed?.error }
  }

  // 確定できるのは当日・前日のみ（仕様書7.2）。期間外の日で入力させると、確定時に
  // BACKDATE_LIMIT_EXCEEDEDとなり入力内容が失われるため、その前に閲覧画面へ誘導する。
  // 遷移元（カレンダー等）でも同じ判定を行うが、URL直接指定に対する受け皿として残す。
  if (!isFinalizableDate(targetDate, today.data.logical_date)) {
    return { kind: 'REDIRECT_VIEW' }
  }

  // 表示対象の全カテゴリが確定済みは変更不可（仕様書7.2）。閲覧画面へ誘導する。
  if (isAllCategoriesReported(presence, toCategoryReportedState(record.data))) {
    return { kind: 'REDIRECT_VIEW' }
  }

  return { kind: 'EDITABLE', record: record.data, quota: quota.data }
}
