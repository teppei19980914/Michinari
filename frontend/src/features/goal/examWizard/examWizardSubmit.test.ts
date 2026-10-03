import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAndAllocateSimpleSlots, replaceMaterials, replaceSubjects } from './examWizardSubmit'

const createSubject = vi.hoisted(() => vi.fn())
const deleteSubject = vi.hoisted(() => vi.fn())
const createMaterial = vi.hoisted(() => vi.fn())
const deleteMaterial = vi.hoisted(() => vi.fn())
const updateSlotAllocations = vi.hoisted(() => vi.fn())
vi.mock('../../../api/goals', () => ({
  createSubject,
  deleteSubject,
  createMaterial,
  deleteMaterial,
  updateSlotAllocations,
}))

const createSlot = vi.hoisted(() => vi.fn())
vi.mock('../../../api/resources', () => ({ createSlot }))

const GOAL_ID = 5

beforeEach(() => {
  vi.clearAllMocks()
})

describe('replaceSubjects', () => {
  it('deletes previously created subjects before creating the current drafts', async () => {
    createSubject.mockResolvedValueOnce({ id: 101, name: '科目A' })
    createSubject.mockResolvedValueOnce({ id: 102, name: '科目B' })

    const result = await replaceSubjects(
      GOAL_ID,
      [
        { name: '科目A', passingScore: '60', examDateType: 'RANGE', examDateFrom: '2026-10-01', examDateTo: '2026-10-31', examDateFixed: '' },
        { name: '科目B', passingScore: '60', examDateType: 'RANGE', examDateFrom: '2026-10-01', examDateTo: '2026-10-31', examDateFixed: '' },
      ],
      [1, 2],
    )

    expect(deleteSubject).toHaveBeenCalledTimes(2)
    expect(deleteSubject).toHaveBeenNthCalledWith(1, 1)
    expect(deleteSubject).toHaveBeenNthCalledWith(2, 2)
    expect(createSubject).toHaveBeenCalledTimes(2)
    expect(result.map((s) => s.id)).toEqual([101, 102])
  })

  it('skips deletion when there is nothing to delete', async () => {
    createSubject.mockResolvedValue({ id: 201, name: '科目A' })

    await replaceSubjects(GOAL_ID, [{ name: '科目A', passingScore: '60', examDateType: 'FIXED', examDateFrom: '', examDateTo: '', examDateFixed: '2026-11-01' }], [])

    expect(deleteSubject).not.toHaveBeenCalled()
  })
})

describe('replaceMaterials', () => {
  it('resolves subject ids from the given map and recreates after deleting old ones', async () => {
    createMaterial.mockResolvedValue({ id: 301 })

    await replaceMaterials(
      GOAL_ID,
      [{ name: '教科書', unitLabel: 'ページ', totalAmount: '500', plannedCycles: '1', subjectNames: ['科目A'] }],
      [11],
      { 科目A: 101 },
      '2026-09-01',
    )

    expect(deleteMaterial).toHaveBeenCalledWith(11)
    expect(createMaterial).toHaveBeenCalledWith(GOAL_ID, {
      name: '教科書',
      unit_label: 'ページ',
      total_amount: 500,
      planned_cycles: 1,
      subject_ids: [101],
      start_date: '2026-09-01',
      due_date_is_manual: false,
      required_environment: 'ANY',
      quality_metric_type: 'NONE',
    })
  })
})

describe('createAndAllocateSimpleSlots', () => {
  it('creates only a weekday slot and allocates its full duration when weekend hours are 0', async () => {
    createSlot.mockResolvedValue({ id: 501 })

    await createAndAllocateSimpleSlots(GOAL_ID, 2, 0)

    expect(createSlot).toHaveBeenCalledOnce()
    expect(createSlot).toHaveBeenCalledWith(
      // environment はスロット自体の性質を表す列であり、`ANY`（制約なし）を許容しない
      // （実機確認済み、resource_service._validate_slot_fields）。
      expect.objectContaining({
        start_time: '20:00',
        end_time: '22:00',
        environment: 'PC',
        weekdays: [0, 1, 2, 3, 4],
      }),
    )
    expect(updateSlotAllocations).toHaveBeenCalledWith(GOAL_ID, {
      allocations: [{ slot_id: 501, minutes: 120 }],
    })
  })

  it('creates both slots when both hours are entered', async () => {
    createSlot.mockResolvedValueOnce({ id: 501 }).mockResolvedValueOnce({ id: 502 })

    await createAndAllocateSimpleSlots(GOAL_ID, 2, 3)

    expect(createSlot).toHaveBeenCalledTimes(2)
    expect(updateSlotAllocations).toHaveBeenCalledWith(GOAL_ID, {
      allocations: [
        { slot_id: 501, minutes: 120 },
        { slot_id: 502, minutes: 180 },
      ],
    })
  })

  it('does nothing when both hours are 0', async () => {
    await createAndAllocateSimpleSlots(GOAL_ID, 0, 0)

    expect(createSlot).not.toHaveBeenCalled()
    expect(updateSlotAllocations).not.toHaveBeenCalled()
  })
})
