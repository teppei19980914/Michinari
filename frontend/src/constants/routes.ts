/**
 * 画面遷移先のパス定数（仕様書5章）。コンポーネント内にパス文字列を直接書かない
 * （CODING_RULES.md 置き場所ルール）。
 *
 * ROUTE_PATTERNSはReact Routerの<Route path>用（`:param`形式）、
 * ROUTESはリンク生成用（実際の値を埋め込んだパスを返す）。
 */
export const ROUTE_PATTERNS = {
  dashboard: '/',
  goals: '/goals',
  goalDetail: '/goals/:goalId',
  goalExport: '/goals/:goalId/export',
  goalResult: '/goals/:goalId/result',
  resources: '/resources',
  calendar: '/calendar',
  analytics: '/analytics',
  settings: '/settings',
  settingsData: '/settings/data',
  dailyReport: '/records/:date/report',
  dailyReportProgress: '/records/:date/progress',
  dailyReportView: '/records/:date/view',
} as const

export const ROUTES = {
  dashboard: ROUTE_PATTERNS.dashboard,
  goals: ROUTE_PATTERNS.goals,
  goalDetail: (goalId: number) => `/goals/${goalId}`,
  goalExport: (goalId: number) => `/goals/${goalId}/export`,
  goalResult: (goalId: number) => `/goals/${goalId}/result`,
  resources: ROUTE_PATTERNS.resources,
  calendar: ROUTE_PATTERNS.calendar,
  analytics: ROUTE_PATTERNS.analytics,
  settings: ROUTE_PATTERNS.settings,
  settingsData: ROUTE_PATTERNS.settingsData,
  dailyReport: (date: string) => `/records/${date}/report`,
  dailyReportProgress: (date: string) => `/records/${date}/progress`,
  dailyReportView: (date: string) => `/records/${date}/view`,
} as const
