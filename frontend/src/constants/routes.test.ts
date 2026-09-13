/** 画面遷移パスの生成結果を、React Router へ登録するパターンと突き合わせて固定する。
 *
 * `ROUTE_PATTERNS`（`<Route path>` 用）と `ROUTES`（リンク生成用）は別々に書かれているため、
 * 片方だけ直すと「リンクは作られるがどの画面にも一致しない」状態になる。型検査では
 * どちらも `string` で通ってしまい検出できないため、対応関係をここで固定する
 * （`queryKeys.test.ts` と同じ理由）。 */
import { describe, expect, it } from 'vitest'
import { ROUTES, ROUTE_PATTERNS } from './routes'

const GOAL_ID = 1
const TARGET_DATE = '2026-09-13'

/** `:param` を実際の値へ置き換えた、パターン由来の期待値を組み立てる。 */
function fromPattern(pattern: string, params: Record<string, string>): string {
  return Object.entries(params).reduce(
    (path, [name, value]) => path.replace(`:${name}`, value),
    pattern,
  )
}

describe('ROUTES（パラメータを取るパス）', () => {
  const goalId = String(GOAL_ID)

  it.each([
    ['goalDetail', ROUTES.goalDetail(GOAL_ID), ROUTE_PATTERNS.goalDetail, { goalId }],
    ['goalExport', ROUTES.goalExport(GOAL_ID), ROUTE_PATTERNS.goalExport, { goalId }],
    ['goalResult', ROUTES.goalResult(GOAL_ID), ROUTE_PATTERNS.goalResult, { goalId }],
    ['dailyReport', ROUTES.dailyReport(TARGET_DATE), ROUTE_PATTERNS.dailyReport, { date: TARGET_DATE }],
    [
      'dailyReportProgress',
      ROUTES.dailyReportProgress(TARGET_DATE),
      ROUTE_PATTERNS.dailyReportProgress,
      { date: TARGET_DATE },
    ],
    [
      'dailyReportView',
      ROUTES.dailyReportView(TARGET_DATE),
      ROUTE_PATTERNS.dailyReportView,
      { date: TARGET_DATE },
    ],
  ])('matches the route pattern for %s', (_name, generated, pattern, params) => {
    expect(generated).toBe(fromPattern(pattern, params))
  })

  it('keeps the concrete values so a pattern-wide rename cannot pass unnoticed', () => {
    expect(ROUTES.goalDetail(GOAL_ID)).toBe('/goals/1')
    expect(ROUTES.goalResult(GOAL_ID)).toBe('/goals/1/result')
    expect(ROUTES.dailyReport(TARGET_DATE)).toBe('/records/2026-09-13/report')
  })
})

describe('ROUTES（固定パス）', () => {
  it('reuses the route patterns as they are', () => {
    expect(ROUTES.dashboard).toBe(ROUTE_PATTERNS.dashboard)
    expect(ROUTES.goals).toBe(ROUTE_PATTERNS.goals)
    expect(ROUTES.resources).toBe(ROUTE_PATTERNS.resources)
    expect(ROUTES.calendar).toBe(ROUTE_PATTERNS.calendar)
    expect(ROUTES.analytics).toBe(ROUTE_PATTERNS.analytics)
    expect(ROUTES.settings).toBe(ROUTE_PATTERNS.settings)
    expect(ROUTES.settingsData).toBe(ROUTE_PATTERNS.settingsData)
    expect(ROUTES.settingsSystemInfo).toBe(ROUTE_PATTERNS.settingsSystemInfo)
    expect(ROUTES.help).toBe(ROUTE_PATTERNS.help)
  })

  it('nests the settings sub screens under the settings path', () => {
    // 設定配下は前方一致でナビゲーションの強調表示を出しているため、階層が崩れないことを固定する。
    expect(ROUTE_PATTERNS.settingsData.startsWith(`${ROUTE_PATTERNS.settings}/`)).toBe(true)
    expect(ROUTE_PATTERNS.settingsSystemInfo.startsWith(`${ROUTE_PATTERNS.settings}/`)).toBe(true)
  })
})
