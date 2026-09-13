import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import { findFailedQuery, isAnyLoading, type QueryLike } from '../../utils/queryGuard'
import { isFutureDate } from './finalizableDate'

/** 判定に関与する取得。補助情報（slotNames）は含めない（取得できなくても入力は妨げないため）。 */
export type ProgressOnlyGuardQueries = {
  record: QueryLike<DailyRecordRead>
  quota: QueryLike<QuotaItemRead[]>
  today: QueryLike<TodayRead>
}

/** 進捗のみ登録画面が取るべき表示状態。
 * `EDITABLE`は取得済みのノルマを同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type ProgressOnlyGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'REDIRECT_VIEW' }
  | { kind: 'EDITABLE'; quota: QuotaItemRead[] }

/**
 * SC-07 進捗のみ登録（ProgressOnlyPage）の表示状態を決める純粋関数。
 *
 * ローディング判定・エラー判定・2種類の転送判定が画面の早期returnとして4箇所に散らばって
 * いたものを1箇所へ集約する。取得を1本足すときに直す場所が1つで済み、分岐を純粋関数として
 * 検証できる（CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」。
 * 日次報告のresolveDailyReportGuardと同じ形に揃えている）。
 *
 * 2種類の転送（未来日・資格勉強が確定済み）は遷移先が同じ閲覧画面のため`REDIRECT_VIEW`へ
 * まとめる。どちらの理由で転送されたかは呼び出し側の描画を変えない。
 *
 * @param queries 判定に関与する3本の取得結果
 * @param targetDate 対象日（YYYY-MM-DD）
 */
export function resolveProgressOnlyGuard(
  queries: ProgressOnlyGuardQueries,
  targetDate: string,
): ProgressOnlyGuard {
  const { record, quota, today } = queries
  // エラーメッセージの優先順もこの並び順に従う（先に失敗を検出した取得のエラーを表示する）。
  const allQueries = [record, quota, today]

  if (isAnyLoading(allQueries)) {
    return { kind: 'LOADING' }
  }

  const failed = findFailedQuery(allQueries)
  // この画面は3本すべてが揃わないと描画できない（ノルマ＝入力欄、記録＝確定状況、
  // 本日＝未来日判定）。取得は成功扱いでもデータが無ければ同様にエラーとする。
  if (failed || record.data === undefined || quota.data === undefined || today.data === undefined) {
    return { kind: 'ERROR', error: failed?.error }
  }

  // 未来日への実績登録はサーバが拒否する（仕様書7.2）。入力させてから送信時に弾くと入力内容が
  // 失われるため、その前に閲覧画面へ誘導する（日次報告画面の入力可能期間ガードと同じ方針）。
  if (isFutureDate(targetDate, today.data.logical_date)) {
    return { kind: 'REDIRECT_VIEW' }
  }

  // この画面はEXAM専用（study_logsのみ扱う）のため、資格勉強が確定済みなら
  // 変更不可（仕様書7.2）。閲覧画面へ誘導する。
  if (record.data.exam_record_state === 'REPORTED') {
    return { kind: 'REDIRECT_VIEW' }
  }

  return { kind: 'EDITABLE', quota: quota.data }
}
