import { describe, expect, it } from 'vitest'
import type { ActiveReadingBook, ActiveWorkAssignment } from '../../api/goals'
import type { QuotaItemRead } from '../../api/records'
import {
  buildBookLabels,
  buildMaterialLabels,
  buildWorkAssignmentLabels,
} from './summaryLabels'

const QUOTA_ITEM = {
  material_id: 10,
  material_name: 'material-name',
  unit_label: 'page',
  quality_metric_type: 'SUBJECTIVE',
} as QuotaItemRead

const READING_BOOK = {
  book: { id: 20, title: 'book-title' },
} as ActiveReadingBook

const WORK_ASSIGNMENT = {
  workAssignment: { id: 30, client_name: 'client-name' },
} as ActiveWorkAssignment

describe('buildMaterialLabels', () => {
  it('maps the material id to the fields the summary needs', () => {
    expect(buildMaterialLabels([QUOTA_ITEM]).get(QUOTA_ITEM.material_id)).toEqual({
      name: 'material-name',
      unitLabel: 'page',
      qualityMetricType: 'SUBJECTIVE',
    })
  })

  it('returns an empty map when there is no quota', () => {
    expect(buildMaterialLabels([]).size).toBe(0)
  })
})

describe('buildBookLabels', () => {
  it('maps the book id to its title', () => {
    expect(buildBookLabels([READING_BOOK]).get(READING_BOOK.book.id)).toEqual({
      title: 'book-title',
    })
  })
})

describe('buildWorkAssignmentLabels', () => {
  it('maps the assignment id to its client name', () => {
    expect(
      buildWorkAssignmentLabels([WORK_ASSIGNMENT]).get(WORK_ASSIGNMENT.workAssignment.id),
    ).toEqual({ clientName: 'client-name' })
  })

  it('keeps a missing client name as null so the caller can show its own fallback', () => {
    const withoutClient = {
      workAssignment: { id: 31, client_name: null },
    } as ActiveWorkAssignment
    expect(buildWorkAssignmentLabels([withoutClient]).get(31)).toEqual({ clientName: null })
  })
})
