/**
 * 画面遷移先のパス定数（仕様書5章）。コンポーネント内にパス文字列を直接書かない
 * （CODING_RULES.md 置き場所ルール）。SC-06/07/08はPhase8で実装するため、
 * 本フェーズでは準備中プレースホルダーへ遷移する。
 *
 * ROUTE_PATTERNSはReact Routerの<Route path>用（`:param`形式）、
 * ROUTESはリンク生成用（実際の値を埋め込んだパスを返す）。
 */
export const ROUTE_PATTERNS = {
  dashboard: '/',
  goals: '/goals',
  goalDetail: '/goals/:goalId',
  calendar: '/calendar',
  analytics: '/analytics',
  settings: '/settings',
  dailyReport: '/records/:date/report',
  dailyReportView: '/records/:date/view',
} as const

export const ROUTES = {
  dashboard: ROUTE_PATTERNS.dashboard,
  goals: ROUTE_PATTERNS.goals,
  goalDetail: (goalId: number) => `/goals/${goalId}`,
  calendar: ROUTE_PATTERNS.calendar,
  analytics: ROUTE_PATTERNS.analytics,
  settings: ROUTE_PATTERNS.settings,
  dailyReport: (date: string) => `/records/${date}/report`,
  dailyReportView: (date: string) => `/records/${date}/view`,
} as const
