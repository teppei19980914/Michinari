import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { resolveZeroRecordMessage } from './zeroRecordMessage'

describe('resolveZeroRecordMessage', () => {
  it('returns the plan-day message for PLAN', () => {
    expect(resolveZeroRecordMessage('PLAN')).toBe(t('dailyReport.zeroRecord.planDayMessage'))
  })

  it('returns the rest-day message for BUFFER', () => {
    expect(resolveZeroRecordMessage('BUFFER')).toBe(t('dailyReport.zeroRecord.restDayMessage'))
  })

  it('returns the rest-day message for OFF', () => {
    expect(resolveZeroRecordMessage('OFF')).toBe(t('dailyReport.zeroRecord.restDayMessage'))
  })
})
