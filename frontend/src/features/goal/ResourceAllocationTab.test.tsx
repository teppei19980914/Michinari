/** リソース配分タブの送信内容と、超過・時間枠なしの表示を固定する（Phase 35）。
 *
 * 配分は日次ノルマの算出根拠になるため、未入力の枠も0分として送る必要がある
 * （送らないとサーバ側で行が消えず、消したはずの配分が残る）。入力値の解釈と合計・超過判定は
 * `slotAllocationForm.test.ts` が担うため、ここでは結線と表示の切り替えを確かめる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, SLOT_ID, makeGoalDetail, makeSlotAllocation } from '../../test/fixtures'
import { ResourceAllocationTab } from './ResourceAllocationTab'

const listSlotAllocations = vi.hoisted(() => vi.fn())
const updateSlotAllocations = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ listSlotAllocations, updateSlotAllocations }))

const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const minutesInput = () => screen.getByRole('spinbutton')

beforeEach(() => {
  vi.clearAllMocks()
  listSlotAllocations.mockResolvedValue([makeSlotAllocation()])
  updateSlotAllocations.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('ResourceAllocationTab の表示', () => {
  it('tells the user to define slots first when there is none', async () => {
    listSlotAllocations.mockResolvedValue([])
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    expect(await screen.findByText(t('goals.resourceAllocation.noSlots'))).toBeDefined()
    expect(screen.queryByRole('button', { name: t('common.action.save') })).toBeNull()
  })

  it('notes that the allocation is optional for reading goals only', async () => {
    const { unmount } = renderWithProviders(
      <ResourceAllocationTab goal={makeGoalDetail({ category: 'READING' })} readOnly={false} />,
    )
    expect(screen.getByText(t('goals.resourceAllocation.optionalForReading'))).toBeDefined()

    unmount()
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    expect(screen.queryByText(t('goals.resourceAllocation.optionalForReading'))).toBeNull()
  })

  it('prefills the stored minutes and shows the free time of the slot', async () => {
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    await waitFor(() => expect(minutesInput()).toBeDefined())
    // 既に配分済みの30分が初期値。空き時間は枠の長さ60分から他目標の10分を引いた50分。
    expect((minutesInput() as HTMLInputElement).value).toBe('30')
    expect(screen.getByText(`50${t('common.unit.minutes')}`)).toBeDefined()
  })

  it('warns when the slot is already over capacity', async () => {
    listSlotAllocations.mockResolvedValue([makeSlotAllocation({ is_over_capacity: true })])
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    expect(await screen.findByText(t('goals.resourceAllocation.overCapacity'))).toBeDefined()
  })

  it('warns as soon as the entered minutes exceed the free time', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    await waitFor(() => expect(minutesInput()).toBeDefined())
    expect(screen.queryByText(t('goals.resourceAllocation.exceeded'))).toBeNull()

    await user.clear(minutesInput())
    await user.type(minutesInput(), '60')

    expect(screen.getByText(t('goals.resourceAllocation.exceeded'))).toBeDefined()
  })

  it('disables the input and hides saving when read only', async () => {
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly />)

    await waitFor(() => expect(minutesInput()).toBeDefined())
    expect((minutesInput() as HTMLInputElement).disabled).toBe(true)
    expect(screen.queryByRole('button', { name: t('common.action.save') })).toBeNull()
  })
})

describe('ResourceAllocationTab の送信内容', () => {
  it('sends the edited minutes and reports success', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    await waitFor(() => expect(minutesInput()).toBeDefined())
    await user.clear(minutesInput())
    await user.type(minutesInput(), '45')
    await user.click(saveButton())

    await waitFor(() => expect(updateSlotAllocations).toHaveBeenCalledOnce())
    expect(updateSlotAllocations).toHaveBeenCalledWith(GOAL_ID, {
      allocations: [{ slot_id: SLOT_ID, minutes: 45 }],
    })
    expect(await screen.findByText(t('common.saveSucceeded'))).toBeDefined()
  })

  it('sends zero for a slot the user emptied so the stored allocation is removed', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ResourceAllocationTab goal={makeGoalDetail()} readOnly={false} />)

    await waitFor(() => expect(minutesInput()).toBeDefined())
    await user.clear(minutesInput())
    await user.click(saveButton())

    await waitFor(() => expect(updateSlotAllocations).toHaveBeenCalledOnce())
    expect(updateSlotAllocations).toHaveBeenCalledWith(GOAL_ID, {
      allocations: [{ slot_id: SLOT_ID, minutes: 0 }],
    })
  })
})
