/** キャッシュキーの実際の値を固定する。
 *
 * キーが変わるとキャッシュが別物として扱われ、「無効化したのに古い値が残る」「取得し直しが
 * 走り続ける」といった、型検査でもテストでも表に出にくい不具合になる。各画面に散在していた
 * 文字列を1箇所へ集約した際の値と一致していることを、ここで明示的に固定する。
 *
 * 前方一致に依存する組み合わせ（calendar / retrospective / workReport）は、短いキーが長い
 * キーの先頭と一致することも検証する。TanStack Query の invalidateQueries はこの前方一致で
 * 関連クエリをまとめて無効化しており、崩れると片方だけ更新されなくなる。 */
import { describe, expect, it } from 'vitest'
import { QUERY_KEYS } from './queryKeys'

const GOAL_ID = 1
const TARGET_DATE = '2026-09-13'

describe('QUERY_KEYS', () => {
  it('keeps the goal keys', () => {
    expect(QUERY_KEYS.goals()).toEqual(['goals'])
    expect(QUERY_KEYS.goal(GOAL_ID)).toEqual(['goal', GOAL_ID])
    expect(QUERY_KEYS.goalSlotAllocations(GOAL_ID)).toEqual(['goal-slot-allocations', GOAL_ID])
    expect(QUERY_KEYS.materialSlotCheck(30)).toEqual(['material-slot-check', 30])
  })

  it('keeps a null goal id in the key so the disabled query can switch over untouched', () => {
    expect(QUERY_KEYS.goal(null)).toEqual(['goal', null])
  })

  it('keeps the daily record keys', () => {
    expect(QUERY_KEYS.record(TARGET_DATE)).toEqual(['record', TARGET_DATE])
    expect(QUERY_KEYS.quota(TARGET_DATE)).toEqual(['quota', TARGET_DATE])
    expect(QUERY_KEYS.today()).toEqual(['today'])
    expect(QUERY_KEYS.dashboard()).toEqual(['dashboard'])
    expect(QUERY_KEYS.dailyMessage()).toEqual(['daily-message'])
    expect(QUERY_KEYS.activeReadingBooks()).toEqual(['activeReadingBooks'])
    expect(QUERY_KEYS.activeWorkAssignments()).toEqual(['activeWorkAssignments'])
  })

  it('keeps the analytics keys', () => {
    expect(QUERY_KEYS.analyticsBaselines(GOAL_ID)).toEqual(['analytics', 'baselines', GOAL_ID])
    expect(QUERY_KEYS.analyticsForecast(GOAL_ID)).toEqual(['analytics', 'forecast', GOAL_ID])
    expect(QUERY_KEYS.analyticsGantt(GOAL_ID)).toEqual(['analytics', 'gantt', GOAL_ID])
    expect(QUERY_KEYS.analyticsGrowthDescriptions(GOAL_ID)).toEqual([
      'analytics',
      'growth-descriptions',
      GOAL_ID,
    ])
    expect(QUERY_KEYS.analyticsProgress(GOAL_ID)).toEqual(['analytics', 'progress', GOAL_ID])
    expect(QUERY_KEYS.analyticsQuality(GOAL_ID, 'WEEK')).toEqual([
      'analytics',
      'quality',
      GOAL_ID,
      'WEEK',
    ])
    expect(QUERY_KEYS.analyticsReadingLogs(GOAL_ID)).toEqual([
      'analytics',
      'reading-logs',
      GOAL_ID,
    ])
    expect(QUERY_KEYS.analyticsSpeed(GOAL_ID)).toEqual(['analytics', 'speed', GOAL_ID])
    expect(QUERY_KEYS.analyticsWorkLogs(GOAL_ID)).toEqual(['analytics', 'work-logs', GOAL_ID])
  })

  it('keeps the settings and system keys', () => {
    expect(QUERY_KEYS.resourceSlots()).toEqual(['resource-slots'])
    expect(QUERY_KEYS.resourceAllocation()).toEqual(['resource-allocation'])
    expect(QUERY_KEYS.dayTypeDefaults()).toEqual(['day-type-defaults'])
    expect(QUERY_KEYS.dayBoundaryHour()).toEqual(['day-boundary-hour'])
    expect(QUERY_KEYS.holidayTreatAsBuffer()).toEqual(['holiday-treat-as-buffer'])
    expect(QUERY_KEYS.settings()).toEqual(['settings'])
    expect(QUERY_KEYS.systemInfo()).toEqual(['systemInfo'])
    expect(QUERY_KEYS.backups()).toEqual(['backups'])
    expect(QUERY_KEYS.aiStatus()).toEqual(['ai-status'])
    expect(QUERY_KEYS.aiAssistants()).toEqual(['ai-assistants'])
    expect(QUERY_KEYS.promptTemplates()).toEqual(['prompt-templates'])
    expect(QUERY_KEYS.knowledgeExportProgress(GOAL_ID)).toEqual([
      'knowledgeExportProgress',
      GOAL_ID,
    ])
  })

  describe('keys that are invalidated by prefix', () => {
    /** 短いキーが長いキーの先頭と一致していること（invalidateQueriesの前方一致の前提）。 */
    function expectPrefixOf(prefix: readonly unknown[], full: readonly unknown[]) {
      expect(full.slice(0, prefix.length)).toEqual([...prefix])
      expect(full.length).toBeGreaterThan(prefix.length)
    }

    it('invalidates the calendar range through the calendar key', () => {
      expect(QUERY_KEYS.calendar()).toEqual(['calendar'])
      expect(QUERY_KEYS.calendarRange('2026-09-01', '2026-09-30')).toEqual([
        'calendar',
        '2026-09-01',
        '2026-09-30',
      ])
      expectPrefixOf(QUERY_KEYS.calendar(), QUERY_KEYS.calendarRange('2026-09-01', '2026-09-30'))
    })

    it('invalidates the retrospective of both anonymize settings', () => {
      expect(QUERY_KEYS.retrospective(GOAL_ID)).toEqual(['retrospective', GOAL_ID])
      expect(QUERY_KEYS.retrospectiveView(GOAL_ID, true)).toEqual([
        'retrospective',
        GOAL_ID,
        true,
      ])
      expectPrefixOf(
        QUERY_KEYS.retrospective(GOAL_ID),
        QUERY_KEYS.retrospectiveView(GOAL_ID, false),
      )
    })

    it('invalidates every period of a work report', () => {
      expect(QUERY_KEYS.workReport('monthly', GOAL_ID)).toEqual(['workReport', 'monthly', GOAL_ID])
      expect(QUERY_KEYS.workReportPeriod('monthly', GOAL_ID, '2026-09')).toEqual([
        'workReport',
        'monthly',
        GOAL_ID,
        '2026-09',
      ])
      expectPrefixOf(
        QUERY_KEYS.workReport('semiannual', GOAL_ID),
        QUERY_KEYS.workReportPeriod('semiannual', GOAL_ID, '2026-H1'),
      )
    })
  })
})
