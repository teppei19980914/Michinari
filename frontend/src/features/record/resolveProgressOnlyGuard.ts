import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
  type CategoryPresence,
} from './categoryCompletion'
import { findFailedQuery, isAnyLoading, type QueryLike } from '../../utils/queryGuard'
import { isFutureDate } from './finalizableDate'

/** 判定に関与する取得。補助情報（slotNames）は含めない（取得できなくても入力は妨げないため）。 */
export type ProgressOnlyGuardQueries = {
  record: QueryLike<DailyRecordRead>
  quota: QueryLike<QuotaItemRead[]>
  readingBooks: QueryLike<unknown>
  workAssignments: QueryLike<unknown>
  goals: QueryLike<unknown>
  today: QueryLike<TodayRead>
}

/** 進捗のみ登録画面が取るべき表示状態。
 * `EDITABLE`は取得済みの記録・ノルマを同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type ProgressOnlyGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'REDIRECT_VIEW' }
  | { kind: 'EDITABLE'; record: DailyRecordRead; quota: QuotaItemRead[] }

/**
 * SC-07 進捗のみ登録（ProgressOnlyPage）の表示状態を決める純粋関数。
 *
 * ローディング判定・エラー判定・2種類の転送判定が画面の早期returnとして4箇所に散らばって
 * いたものを1箇所へ集約する。取得を1本足すときに直す場所が1つで済み、分岐を純粋関数として
 * 検証できる（CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」。
 * 日次報告のresolveDailyReportGuardと同じ形に揃えている）。
 *
 * 2種類の転送（未来日・登録できるカテゴリが残っていない）は遷移先が同じ閲覧画面のため
 * `REDIRECT_VIEW`へまとめる。どちらの理由で転送されたかは呼び出し側の描画を変えない。
 *
 * 確定済み判定にはカテゴリ別の状態（isAllCategoriesReported）を使う。以前は資格勉強
 * （exam_record_state）だけを見て転送していたため、資格勉強を確定した日は読書・仕事が
 * 未入力でも閲覧画面へ飛ばされ、進捗を登録する手段が無かった（日次報告で2026-09-12に
 * 是正した不具合、仕様書1.1（改20）と同型）。
 *
 * @param queries 判定に関与する6本の取得結果
 * @param presence その日そのカテゴリに登録すべき対象があるか（resolveVisibleReportTargets）
 * @param targetDate 対象日（YYYY-MM-DD）
 */
export function resolveProgressOnlyGuard(
  queries: ProgressOnlyGuardQueries,
  presence: CategoryPresence,
  targetDate: string,
): ProgressOnlyGuard {
  const { record, quota, readingBooks, workAssignments, goals, today } = queries
  // エラーメッセージの優先順もこの並び順に従う（先に失敗を検出した取得のエラーを表示する）。
  const allQueries = [record, quota, readingBooks, workAssignments, goals, today]

  if (isAnyLoading(allQueries)) {
    return { kind: 'LOADING' }
  }

  const failed = findFailedQuery(allQueries)
  // 取得済みデータの有無まで要求するのはこの4本のみ。readingBooks・workAssignmentsは
  // 以降も`?? []`として扱い、取得できなくても他カテゴリの入力を妨げない
  // （resolveDailyReportGuardと同じ扱い）。
  if (
    failed ||
    record.data === undefined ||
    quota.data === undefined ||
    goals.data === undefined ||
    today.data === undefined
  ) {
    return { kind: 'ERROR', error: failed?.error }
  }

  // 未来日への実績登録はサーバが拒否する（仕様書7.2）。入力させてから送信時に弾くと入力内容が
  // 失われるため、その前に閲覧画面へ誘導する（日次報告画面の入力可能期間ガードと同じ方針）。
  if (isFutureDate(targetDate, today.data.logical_date)) {
    return { kind: 'REDIRECT_VIEW' }
  }

  // 登録対象のあるカテゴリがすべて確定済みなら、この画面でできることは無い（仕様書7.2）。
  // 閲覧画面へ誘導する。
  if (isAllCategoriesReported(presence, toCategoryReportedState(record.data))) {
    return { kind: 'REDIRECT_VIEW' }
  }

  return { kind: 'EDITABLE', record: record.data, quota: quota.data }
}
