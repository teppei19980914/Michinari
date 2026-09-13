/** 月次報告・半期評価の呼び分けを固定する（Phase 36）。
 *
 * 取り違えても画面の形は同じで、月次報告の画面から半期評価を読み書きしてしまう事故が
 * 画面上では見分けられない。種別ごとに何を呼ぶかをここで押さえる。 */
import { describe, expect, it } from 'vitest'
import {
  generateMonthlyReport,
  generateSemiannualReview,
  getMonthlyReport,
  getSemiannualReview,
  updateMonthlyReport,
  updateSemiannualReview,
} from '../../api/closure'
import { resolveWorkReportKind } from './workReportKind'

describe('resolveWorkReportKind', () => {
  it('binds the monthly report endpoints for the monthly kind', () => {
    const config = resolveWorkReportKind('monthly')
    expect(config.getReport).toBe(getMonthlyReport)
    expect(config.generateReport).toBe(generateMonthlyReport)
    expect(config.updateReport).toBe(updateMonthlyReport)
  })

  it('binds the semiannual review endpoints for the semiannual kind', () => {
    const config = resolveWorkReportKind('semiannual')
    expect(config.getReport).toBe(getSemiannualReview)
    expect(config.generateReport).toBe(generateSemiannualReview)
    expect(config.updateReport).toBe(updateSemiannualReview)
  })

  it('offers the notes field only for the monthly report', () => {
    // 半期評価は特記事項を持たないため、入力欄も送信内容からも外す。
    expect(resolveWorkReportKind('monthly').showReportNotes).toBe(true)
    expect(resolveWorkReportKind('semiannual').showReportNotes).toBe(false)
  })

  it('labels the period and the next goal per kind', () => {
    const monthly = resolveWorkReportKind('monthly')
    const semiannual = resolveWorkReportKind('semiannual')
    expect(monthly.periodLabelKey).not.toBe(semiannual.periodLabelKey)
    expect(monthly.nextGoalTextLabelKey).not.toBe(semiannual.nextGoalTextLabelKey)
    expect(monthly.periodPlaceholder).not.toBe(semiannual.periodPlaceholder)
  })
})
