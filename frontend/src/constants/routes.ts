/**
 * 画面遷移先のパス定数（仕様書5章）。コンポーネント内にパス文字列を直接書かない
 * （CODING_RULES.md 置き場所ルール）。
 *
 * ROUTE_PATTERNSはReact Routerの<Route path>用（`:param`形式）、
 * ROUTESはリンク生成用（実際の値を埋め込んだパスを返す）。
 */
export const ROUTE_PATTERNS = {
  dashboard: '/',
  welcome: '/welcome',
  goals: '/goals',
  goalNewExam: '/goals/new/exam',
  goalDetail: '/goals/:goalId',
  goalExport: '/goals/:goalId/export',
  goalResult: '/goals/:goalId/result',
  attachments: '/attachments',
  bookshelf: '/bookshelf',
  bookDetail: '/bookshelf/:goalId',
  resources: '/resources',
  calendar: '/calendar',
  analytics: '/analytics',
  settings: '/settings',
  settingsData: '/settings/data',
  settingsSystemInfo: '/settings/system-info',
  dailyReport: '/records/:date/report',
  dailyReportProgress: '/records/:date/progress',
  dailyReportView: '/records/:date/view',
  recapTheme: '/recap-themes/:themeId',
  quiz: '/quiz',
  vocab: '/vocab',
  vocabDeck: '/vocab/:deckId',
  vocabQuiz: '/vocab/:deckId/quiz',
  //: 全画面ヘッダーの単語帳タブ→目標クリックの直接遷移先（開発Todo_単語帳_出題導線改修
  //: _v1.0 U6・D6）。1目標1デッキのため、ここでgoalIdからdeckIdを解決してvocabQuizへ
  //: 中継する。
  vocabGoalQuiz: '/vocab/by-goal/:goalId/quiz',
  help: '/help',
} as const

export const ROUTES = {
  dashboard: ROUTE_PATTERNS.dashboard,
  welcome: ROUTE_PATTERNS.welcome,
  goals: ROUTE_PATTERNS.goals,
  goalNewExam: ROUTE_PATTERNS.goalNewExam,
  goalDetail: (goalId: number) => `/goals/${goalId}`,
  //: スケジュールタブへの直接リンク（日次報告・ダッシュボードの修正案の案内、
  //: 開発Todo_スケジュール・ガントチャート_v1.1 13.8、単位5）。
  goalScheduleTab: (goalId: number) => `/goals/${goalId}?tab=schedule`,
  goalExport: (goalId: number) => `/goals/${goalId}/export`,
  goalResult: (goalId: number) => `/goals/${goalId}/result`,
  attachments: ROUTE_PATTERNS.attachments,
  bookshelf: ROUTE_PATTERNS.bookshelf,
  bookDetail: (goalId: number) => `/bookshelf/${goalId}`,
  resources: ROUTE_PATTERNS.resources,
  calendar: ROUTE_PATTERNS.calendar,
  analytics: ROUTE_PATTERNS.analytics,
  settings: ROUTE_PATTERNS.settings,
  settingsData: ROUTE_PATTERNS.settingsData,
  settingsSystemInfo: ROUTE_PATTERNS.settingsSystemInfo,
  dailyReport: (date: string) => `/records/${date}/report`,
  dailyReportProgress: (date: string) => `/records/${date}/progress`,
  dailyReportView: (date: string) => `/records/${date}/view`,
  recapTheme: (themeId: number) => `/recap-themes/${themeId}`,
  quiz: ROUTE_PATTERNS.quiz,
  vocab: ROUTE_PATTERNS.vocab,
  vocabDeck: (deckId: number) => `/vocab/${deckId}`,
  vocabQuiz: (deckId: number) => `/vocab/${deckId}/quiz`,
  vocabGoalQuiz: (goalId: number) => `/vocab/by-goal/${goalId}/quiz`,
  help: ROUTE_PATTERNS.help,
} as const
