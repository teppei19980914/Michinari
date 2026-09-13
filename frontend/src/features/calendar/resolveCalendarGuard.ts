import type { CalendarDayRead } from '../../api/calendar'
import type { TodayRead } from '../../api/records'
import { findFailedQuery, isAnyLoading, type QueryLike } from '../../utils/queryGuard'

/** 判定に関与する取得。選択中の目標の詳細（補助表示用）は含めない。
 * 目標が未選択の間は`enabled: false`で待機しており、待たせると画面が出せないため。 */
export type CalendarGuardQueries = {
  today: QueryLike<TodayRead>
  calendar: QueryLike<CalendarDayRead[]>
  goals: QueryLike<unknown>
}

/** カレンダー画面が取るべき表示状態。
 * `READY`は取得済みの本日・日別情報を同伴し、呼び出し側が非nullアサーションを書かずに済むようにする。 */
export type CalendarGuard =
  | { kind: 'LOADING' }
  | { kind: 'ERROR'; error: unknown }
  | { kind: 'READY'; today: TodayRead; days: CalendarDayRead[] }

/**
 * SC-05 カレンダー（CalendarPage）の表示状態を決める純粋関数。
 *
 * ローディング判定とエラー判定が画面の早期returnとして並記されており、取得を1本足すたびに
 * 2箇所の羅列を直す必要があった。判定を1箇所へ集約し、分岐を純粋関数として検証できるように
 * する（CODING_RULES.md「フロントの分岐は`.ts`へ切り出す」「①DRYの原則」）。
 *
 * @param queries 判定に関与する3本の取得結果
 */
export function resolveCalendarGuard(queries: CalendarGuardQueries): CalendarGuard {
  const { today, calendar, goals } = queries
  // エラーメッセージの優先順もこの並び順に従う（先に失敗を検出した取得のエラーを表示する）。
  const allQueries = [today, calendar, goals]

  if (isAnyLoading(allQueries)) {
    return { kind: 'LOADING' }
  }

  const failed = findFailedQuery(allQueries)
  // goalsQueryが失敗すると対象目標を解決できず補助表示が常に空になってしまうため、
  // 他の必須クエリと同様にエラー画面を表示する。ただしデータの有無までは要求しない。
  // 以降goalsは`?? []`として扱い、目標が0件の場合と同じ表示になれば足りる。
  if (failed || today.data === undefined || calendar.data === undefined) {
    return { kind: 'ERROR', error: failed?.error }
  }

  return { kind: 'READY', today: today.data, days: calendar.data }
}
