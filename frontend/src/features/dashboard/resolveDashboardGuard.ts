import type { DashboardRead } from '../../api/dashboard'
import { findFailedQuery, isAnyLoading, type QueryLike } from '../../utils/queryGuard'

/** 判定に関与する取得。今日の一言（TodayMessage）は含めない。
 * 非同期に後から差し込む補助表示であり、待たせると初期表示2秒以内の要件に反するため。 */
export type DashboardGuardQueries = {
  dashboard: QueryLike<DashboardRead>
  goals: QueryLike<unknown>
}

/** ダッシュボードが取るべき表示状態。
 * `READY`は取得済みのダッシュボードを同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type DashboardGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'READY'; dashboard: DashboardRead }

/**
 * SC-01 ダッシュボード（DashboardPage）の表示状態を決める純粋関数。
 *
 * ローディング判定とエラー判定が画面の早期returnとして並記されており、取得を1本足すたびに
 * 2箇所の羅列を直す必要があった。判定を1箇所へ集約し、分岐を純粋関数として検証できるように
 * する（CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」）。
 *
 * @param queries 判定に関与する2本の取得結果
 */
export function resolveDashboardGuard(queries: DashboardGuardQueries): DashboardGuard {
  const { dashboard, goals } = queries
  // エラーメッセージの優先順もこの並び順に従う（先に失敗を検出した取得のエラーを表示する）。
  const allQueries = [dashboard, goals]

  if (isAnyLoading(allQueries)) {
    return { kind: 'LOADING' }
  }

  const failed = findFailedQuery(allQueries)
  // 技術選定書7.3「エラーコードに対応するロケール文言を表示する」。goalsQueryが失敗すると
  // 対象目標を解決できず全セクションが空表示になってしまうため、dashboardQueryと同様に
  // エラー画面を表示する（goal_cards等はあるのに何も表示されない状態を避ける）。ただし
  // データの有無までは要求しない。以降goalsは`?? []`として扱い、目標が0件の場合と
  // 同じ表示になれば足りる。
  if (failed || dashboard.data === undefined) {
    return { kind: 'ERROR', error: failed?.error }
  }

  return { kind: 'READY', dashboard: dashboard.data }
}
