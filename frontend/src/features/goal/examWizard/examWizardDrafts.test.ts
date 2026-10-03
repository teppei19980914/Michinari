import { describe, expect, it } from 'vitest'
import {
  buildMaterialCreatePayload,
  buildSubjectCreatePayload,
  emptyMaterialDraft,
  emptySubjectDraft,
  materialDraftFromTemplate,
  subjectDraftFromTemplate,
} from './examWizardDrafts'

describe('subjectDraftFromTemplate', () => {
  it('carries over the name and passing score as a RANGE draft with empty dates', () => {
    expect(subjectDraftFromTemplate({ name: '科目A', passing_score_type: 'PERCENTAGE', passing_score: 60 })).toEqual({
      name: '科目A',
      passingScore: '60',
      examDateType: 'RANGE',
      examDateFrom: '',
      examDateTo: '',
      examDateFixed: '',
    })
  })
})

describe('emptySubjectDraft', () => {
  it('defaults to a 60% RANGE draft', () => {
    expect(emptySubjectDraft()).toMatchObject({ name: '', passingScore: '60', examDateType: 'RANGE' })
  })
})

describe('materialDraftFromTemplate / emptyMaterialDraft', () => {
  it('carries over every field from the template material', () => {
    expect(
      materialDraftFromTemplate({
        name: '教科書',
        unit_label: 'ページ',
        total_amount: 500,
        planned_cycles: 2,
        subject_names: ['科目A', '科目B'],
      }),
    ).toEqual({
      name: '教科書',
      unitLabel: 'ページ',
      totalAmount: '500',
      plannedCycles: '2',
      subjectNames: ['科目A', '科目B'],
    })
  })

  it('defaults planned cycles to 1 for a manually added material', () => {
    expect(emptyMaterialDraft()).toMatchObject({ plannedCycles: '1', subjectNames: [] })
  })
})

describe('buildSubjectCreatePayload', () => {
  it('sends only the range dates when examDateType is RANGE', () => {
    expect(
      buildSubjectCreatePayload({
        name: '科目A',
        passingScore: '60',
        examDateType: 'RANGE',
        examDateFrom: '2026-10-01',
        examDateTo: '2026-10-31',
        examDateFixed: '',
      }),
    ).toEqual({
      name: '科目A',
      exam_date_type: 'RANGE',
      exam_date_from: '2026-10-01',
      exam_date_to: '2026-10-31',
      exam_date_fixed: null,
      passing_score_type: 'PERCENTAGE',
      passing_score: 60,
    })
  })

  it('sends only the fixed date when examDateType is FIXED', () => {
    const payload = buildSubjectCreatePayload({
      name: '科目A',
      passingScore: '60',
      examDateType: 'FIXED',
      examDateFrom: '2026-10-01',
      examDateTo: '2026-10-31',
      examDateFixed: '2026-11-15',
    })

    expect(payload.exam_date_from).toBeNull()
    expect(payload.exam_date_to).toBeNull()
    expect(payload.exam_date_fixed).toBe('2026-11-15')
  })

  it('sends a null fixed date when it is left blank', () => {
    const payload = buildSubjectCreatePayload({
      name: '科目A',
      passingScore: '60',
      examDateType: 'FIXED',
      examDateFrom: '',
      examDateTo: '',
      examDateFixed: '',
    })

    expect(payload.exam_date_fixed).toBeNull()
  })

  it('sends null range dates when they are left blank', () => {
    const payload = buildSubjectCreatePayload({
      name: '科目A',
      passingScore: '',
      examDateType: 'RANGE',
      examDateFrom: '',
      examDateTo: '',
      examDateFixed: '',
    })

    expect(payload.exam_date_from).toBeNull()
    expect(payload.exam_date_to).toBeNull()
    expect(payload.passing_score).toBeNull()
  })
})

describe('buildMaterialCreatePayload', () => {
  it('resolves subject names to ids via the given map', () => {
    const payload = buildMaterialCreatePayload(
      {
        name: '教科書',
        unitLabel: 'ページ',
        totalAmount: '500',
        plannedCycles: '2',
        subjectNames: ['科目A', '科目B'],
      },
      { 科目A: 10, 科目B: 11 },
      '2026-09-01',
    )

    expect(payload).toEqual({
      name: '教科書',
      unit_label: 'ページ',
      total_amount: 500,
      planned_cycles: 2,
      subject_ids: [10, 11],
      start_date: '2026-09-01',
      due_date_is_manual: false,
      required_environment: 'ANY',
      quality_metric_type: 'NONE',
    })
  })

  it('drops subject names that have no matching id', () => {
    const payload = buildMaterialCreatePayload(
      { name: '教科書', unitLabel: 'ページ', totalAmount: '500', plannedCycles: '1', subjectNames: ['未知の科目'] },
      {},
      '2026-09-01',
    )

    expect(payload.subject_ids).toEqual([])
  })

  it('defaults planned cycles to 1 when left blank', () => {
    const payload = buildMaterialCreatePayload(
      { name: '教科書', unitLabel: 'ページ', totalAmount: '500', plannedCycles: '', subjectNames: ['科目A'] },
      { 科目A: 1 },
      '2026-09-01',
    )

    expect(payload.planned_cycles).toBe(1)
  })
})
