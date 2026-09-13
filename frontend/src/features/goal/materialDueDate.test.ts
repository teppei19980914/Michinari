import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { computeAutoDueDate, resolveStartDateError } from './materialDueDate'

describe('computeAutoDueDate', () => {
  const subjects = [
    { id: 1, exam_date_type: 'RANGE' as const, exam_date_from: '2026-10-17', exam_date_fixed: null },
    { id: 2, exam_date_type: 'RANGE' as const, exam_date_from: '2026-08-27', exam_date_fixed: null },
    { id: 3, exam_date_type: 'FIXED' as const, exam_date_from: null, exam_date_fixed: '2026-09-01' },
  ]

  it('returns the day before the earliest effective exam date among selected subjects', () => {
    expect(computeAutoDueDate(subjects, [1, 2])).toBe('2026-08-26')
  })

  it('uses exam_date_fixed for FIXED-type subjects', () => {
    expect(computeAutoDueDate(subjects, [3])).toBe('2026-08-31')
  })

  it('returns null when no subject is selected or no exam date resolves', () => {
    expect(computeAutoDueDate(subjects, [])).toBeNull()
    expect(computeAutoDueDate([{ id: 4, exam_date_type: 'RANGE', exam_date_from: null, exam_date_fixed: null }], [4])).toBeNull()
  })

  it('keeps the earliest date when later subjects have later exam dates', () => {
    // 最も早い受験日が配列の先頭に来る順序（reduce の「更新しない」側）の検証。
    expect(computeAutoDueDate(subjects, [2, 3])).toBe('2026-08-26')
  })
})

describe('resolveStartDateError', () => {
  /** 警告の要否だけを変えたいので、既定は「矛盾なし」の組み合わせにしておく。 */
  const base = {
    startDate: '2026-09-01',
    dueDateIsManual: false,
    dueDate: '',
    autoDueDate: '2026-11-30',
  }

  it('returns null while the start date is before the effective due date', () => {
    expect(resolveStartDateError(base)).toBeNull()
  })

  it('returns null when the start date equals the effective due date', () => {
    // 同日は矛盾ではない（その日1日で終える計画）。
    expect(resolveStartDateError({ ...base, startDate: '2026-11-30' })).toBeNull()
  })

  it('warns with the auto-derived due date while the manual switch is off', () => {
    expect(resolveStartDateError({ ...base, startDate: '2026-12-01' })).toBe(
      t('goals.materials.startDateAfterDueDateError', { dueDate: '2026-11-30' }),
    )
  })

  it('warns with the typed due date while the manual switch is on', () => {
    // 手動指定がonのときは自動導出ではなく入力欄の日付と突き合わせる。
    expect(
      resolveStartDateError({
        ...base,
        startDate: '2026-10-02',
        dueDateIsManual: true,
        dueDate: '2026-10-01',
      }),
    ).toBe(t('goals.materials.startDateAfterDueDateError', { dueDate: '2026-10-01' }))
  })

  it('returns null when the manual switch is on but no due date was entered', () => {
    expect(
      resolveStartDateError({ ...base, startDate: '2026-12-01', dueDateIsManual: true }),
    ).toBeNull()
  })

  it('returns null when no due date can be resolved at all', () => {
    expect(
      resolveStartDateError({ ...base, startDate: '2026-12-01', autoDueDate: null }),
    ).toBeNull()
  })

  it('returns null while the start date is not entered yet', () => {
    expect(resolveStartDateError({ ...base, startDate: '' })).toBeNull()
  })
})
