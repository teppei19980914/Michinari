import { describe, expect, it } from 'vitest'
import { buildReplanHistoryRows } from './replanHistoryRows'

const NAMES = new Map([[1, '教材A']])

describe('buildReplanHistoryRows', () => {
  it('leaves quotaBefore null for the first (INITIAL) baseline of a material', () => {
    const rows = buildReplanHistoryRows(
      [
        {
          id: 1,
          material_id: 1,
          effective_from: '2026-01-01',
          baseline_daily_quota: 10,
          reason: 'INITIAL',
        },
      ],
      NAMES,
    )

    expect(rows).toEqual([
      {
        id: 1,
        materialId: 1,
        materialName: '教材A',
        effectiveFrom: '2026-01-01',
        reason: 'INITIAL',
        quotaBefore: null,
        quotaAfter: 10,
      },
    ])
  })

  it('fills quotaBefore from the chronologically previous baseline of the same material', () => {
    const rows = buildReplanHistoryRows(
      [
        {
          id: 2,
          material_id: 1,
          effective_from: '2026-02-01',
          baseline_daily_quota: 20,
          reason: 'REPLAN',
        },
        {
          id: 1,
          material_id: 1,
          effective_from: '2026-01-01',
          baseline_daily_quota: 10,
          reason: 'INITIAL',
        },
      ],
      NAMES,
    )

    const replanRow = rows.find((r) => r.id === 2)
    expect(replanRow?.quotaBefore).toBe(10)
    expect(replanRow?.quotaAfter).toBe(20)
  })

  it('does not mix baselines across different materials when pairing before/after', () => {
    const rows = buildReplanHistoryRows(
      [
        {
          id: 1,
          material_id: 1,
          effective_from: '2026-01-01',
          baseline_daily_quota: 10,
          reason: 'INITIAL',
        },
        {
          id: 2,
          material_id: 2,
          effective_from: '2026-01-05',
          baseline_daily_quota: 99,
          reason: 'INITIAL',
        },
      ],
      new Map([[1, '教材A'], [2, '教材B']]),
    )

    expect(rows.every((r) => r.quotaBefore === null)).toBe(true)
  })

  it('sorts the returned rows by effective_from descending (newest first)', () => {
    const rows = buildReplanHistoryRows(
      [
        {
          id: 1,
          material_id: 1,
          effective_from: '2026-01-01',
          baseline_daily_quota: 10,
          reason: 'INITIAL',
        },
        {
          id: 2,
          material_id: 1,
          effective_from: '2026-03-01',
          baseline_daily_quota: 30,
          reason: 'REPLAN',
        },
      ],
      NAMES,
    )

    expect(rows.map((r) => r.effectiveFrom)).toEqual(['2026-03-01', '2026-01-01'])
  })

  it('falls back to the material id as the label when the name lookup misses', () => {
    const rows = buildReplanHistoryRows(
      [
        {
          id: 1,
          material_id: 42,
          effective_from: '2026-01-01',
          baseline_daily_quota: 10,
          reason: 'INITIAL',
        },
      ],
      new Map(),
    )

    expect(rows[0].materialName).toBe('42')
  })

  it('returns an empty array when there are no baselines', () => {
    expect(buildReplanHistoryRows([], NAMES)).toEqual([])
  })
})
