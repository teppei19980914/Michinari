import { describe, expect, it } from 'vitest'
import {
  canProceedFromMaterials,
  canProceedFromSubjects,
  isMaterialDraftValid,
  isSubjectDraftValid,
} from './examWizardValidation'

const rangeSubject = {
  name: '科目A',
  passingScore: '60',
  examDateType: 'RANGE' as const,
  examDateFrom: '2026-10-01',
  examDateTo: '2026-10-31',
  examDateFixed: '',
}

describe('isSubjectDraftValid', () => {
  it('requires a name', () => {
    expect(isSubjectDraftValid({ ...rangeSubject, name: '' })).toBe(false)
  })

  it('requires both range dates when RANGE', () => {
    expect(isSubjectDraftValid({ ...rangeSubject, examDateTo: '' })).toBe(false)
    expect(isSubjectDraftValid(rangeSubject)).toBe(true)
  })

  it('requires the fixed date when FIXED', () => {
    const fixed = { ...rangeSubject, examDateType: 'FIXED' as const, examDateFixed: '' }
    expect(isSubjectDraftValid(fixed)).toBe(false)
    expect(isSubjectDraftValid({ ...fixed, examDateFixed: '2026-11-01' })).toBe(true)
  })
})

describe('canProceedFromSubjects', () => {
  it('rejects an empty list (activate requires at least one subject)', () => {
    expect(canProceedFromSubjects([])).toBe(false)
  })

  it('rejects when any subject is invalid', () => {
    expect(canProceedFromSubjects([rangeSubject, { ...rangeSubject, name: '' }])).toBe(false)
  })

  it('accepts when every subject is valid', () => {
    expect(canProceedFromSubjects([rangeSubject])).toBe(true)
  })
})

const material = {
  name: '教科書',
  unitLabel: 'ページ',
  totalAmount: '500',
  plannedCycles: '1',
  subjectNames: ['科目A'],
}

describe('isMaterialDraftValid', () => {
  it('requires a name, unit, non-negative total amount and at least one subject', () => {
    expect(isMaterialDraftValid(material)).toBe(true)
    expect(isMaterialDraftValid({ ...material, name: '' })).toBe(false)
    expect(isMaterialDraftValid({ ...material, unitLabel: '' })).toBe(false)
    expect(isMaterialDraftValid({ ...material, totalAmount: '' })).toBe(false)
    expect(isMaterialDraftValid({ ...material, totalAmount: '-1' })).toBe(false)
    expect(isMaterialDraftValid({ ...material, subjectNames: [] })).toBe(false)
  })
})

describe('canProceedFromMaterials', () => {
  it('rejects an empty list (activate requires at least one material)', () => {
    expect(canProceedFromMaterials([])).toBe(false)
  })

  it('accepts when every material is valid', () => {
    expect(canProceedFromMaterials([material])).toBe(true)
  })
})
