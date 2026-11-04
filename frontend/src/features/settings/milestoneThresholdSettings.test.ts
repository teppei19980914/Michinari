/** 節目の閾値設定の入力判定のテスト（開発Todo_節目のお祝い_v1.0 F-08b）。
 *
 * 受け付ける形式は、バックエンドの `app/services/settings_service.py:
 * _parse_threshold_list` と食い違わないようにする（画面で保存できてもサーバが弾く、
 * という不一致を防ぐ）。 */
import { describe, expect, it } from 'vitest'
import {
  buildMilestoneThresholdSettingsPayload,
  isValidThresholdList,
  resolveMilestoneThresholdGuard,
  type MilestoneThresholdFields,
} from './milestoneThresholdSettings'

const VALID_FIELDS: MilestoneThresholdFields = {
  consecutiveDaysThresholds: '3,7,14',
  totalRecordDaysThresholds: '10,30',
  readingTotalPagesThresholds: '500,1000',
  readingCompletedBooksThresholds: '1,3',
  examOverallProgressThresholds: '25,50,75',
  workRecordCountThresholds: '10,50',
}

describe('isValidThresholdList', () => {
  it.each(['3', '3,7,14', ' 3 , 7 , 14 '])('accepts %s', (value) => {
    expect(isValidThresholdList(value)).toBe(true)
  })

  it.each([
    ['', '空文字'],
    ['3,,7', '空要素を含む'],
    ['3,abc', '数字以外を含む'],
    ['-3', '負の数'],
    ['3.5', '小数'],
    ['3;7', '区切りがカンマでない'],
  ])('rejects %s (%s)', (value) => {
    expect(isValidThresholdList(value)).toBe(false)
  })
})

describe('resolveMilestoneThresholdGuard', () => {
  it('allows saving when every field is a valid comma-separated list', () => {
    expect(resolveMilestoneThresholdGuard(VALID_FIELDS)).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })

  it('blocks saving when any single field is malformed', () => {
    expect(
      resolveMilestoneThresholdGuard({ ...VALID_FIELDS, workRecordCountThresholds: '10,,50' }),
    ).toEqual({
      canSubmit: false,
      errorKey: 'settings.milestoneThreshold.invalid',
    })
  })
})

describe('buildMilestoneThresholdSettingsPayload', () => {
  it('maps every field to its snake_case API key', () => {
    expect(buildMilestoneThresholdSettingsPayload(VALID_FIELDS)).toEqual({
      consecutive_days_thresholds: '3,7,14',
      total_record_days_thresholds: '10,30',
      reading_total_pages_thresholds: '500,1000',
      reading_completed_books_thresholds: '1,3',
      exam_overall_progress_thresholds: '25,50,75',
      work_record_count_thresholds: '10,50',
    })
  })
})
