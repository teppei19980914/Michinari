/** 時間スロットの一覧・追加・編集・削除（仕様書6.3）の送信内容とガードを固定する回帰テスト
 * （Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応でスロットのフォームを
 * 切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * この部品は「新規作成では有効/無効の項目を送らない（作成時は常に有効）」「曜日を1つも
 * 選んでいない間は保存させない」という判定を持つ。いずれも壊れるとスロットが意図しない
 * 状態で保存され、全目標のリソース配分に波及する。削除は取り消せないため、確認ダイアログの
 * ガードも固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { ResourceSlotRead } from '../../api/resources'
import { SlotList } from './SlotList'

const listSlots = vi.hoisted(() => vi.fn())
const createSlot = vi.hoisted(() => vi.fn())
const updateSlot = vi.hoisted(() => vi.fn())
const deleteSlot = vi.hoisted(() => vi.fn())
vi.mock('../../api/resources', () => ({ listSlots, createSlot, updateSlot, deleteSlot }))

const SLOT_ID = 51
const SLOT_NAME = '朝の枠'
/** 月曜（`resources.weekdays.*` のキーに対応する 0=月 始まりの番号）。 */
const MONDAY = 0
const TUESDAY = 1

function makeSlot(overrides: Partial<ResourceSlotRead> = {}): ResourceSlotRead {
  return {
    id: SLOT_ID,
    name: SLOT_NAME,
    start_time: '07:00',
    end_time: '08:00',
    environment: 'PC',
    is_active: true,
    display_order: 1,
    weekdays: [MONDAY],
    duration_minutes: 60,
    duration_hours: 1,
    ...overrides,
  } as ResourceSlotRead
}

// --- 要素アクセサ ---
const addButton = () => screen.getByRole('button', { name: t('resources.slots.addTitle') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const deleteButton = () => screen.getByRole('button', { name: t('common.action.delete') })
const nameInput = () => screen.getByLabelText(t('resources.slots.nameLabel'))
const weekdayCheckbox = (weekday: number) =>
  screen.getByRole('checkbox', { name: t(`resources.weekdays.${weekday}`) })
const isActiveCheckbox = () =>
  screen.queryByRole('checkbox', { name: t('resources.slots.isActiveLabel') })

/** 一覧の取得が反映されるまで待ってから返す（待たないと行のボタンがまだ無い）。 */
async function renderList(slots: ResourceSlotRead[] = []) {
  listSlots.mockResolvedValue(slots)
  const result = renderWithProviders(<SlotList />)
  if (slots.length === 0) {
    await screen.findByText(t('resources.slots.empty'))
  } else {
    await screen.findByText(new RegExp(slots[0].name))
  }
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  createSlot.mockResolvedValue(undefined)
  updateSlot.mockResolvedValue(undefined)
  deleteSlot.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('SlotList の一覧', () => {
  it('tells the user no slot is defined yet', async () => {
    await renderList([])
    expect(screen.getByText(t('resources.slots.empty'))).toBeTruthy()
  })

  it('shows the name, the time range and the weekday initials of each slot', async () => {
    await renderList([makeSlot({ weekdays: [MONDAY, TUESDAY] })])
    expect(screen.getByText(`${SLOT_NAME} (07:00〜08:00)`)).toBeTruthy()
    expect(
      screen.getByText(
        new RegExp(`${t(`resources.weekdays.${MONDAY}`)}${t(`resources.weekdays.${TUESDAY}`)}`),
      ),
    ).toBeTruthy()
  })

  it('marks an inactive slot as disabled in the heading', async () => {
    await renderList([makeSlot({ is_active: false })])
    const heading = screen.getByText(new RegExp(SLOT_NAME))
    expect(heading.textContent).toContain(
      `${t('resources.slots.isActiveLabel')}: ${t('common.no')}`,
    )
  })
})

describe('SlotList の削除', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => false))
    await renderList([makeSlot()])
    await user.click(deleteButton())
    expect(deleteSlot).not.toHaveBeenCalled()
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => true))
    await renderList([makeSlot()])
    await user.click(deleteButton())
    await waitFor(() => expect(deleteSlot).toHaveBeenCalledWith(SLOT_ID))
  })
})

describe('SlotList の追加フォーム', () => {
  it('starts with the default time range and no weekday selected', async () => {
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())

    expect((screen.getByLabelText(t('resources.slots.startTimeLabel')) as HTMLInputElement).value)
      .toBe('07:00')
    expect((screen.getByLabelText(t('resources.slots.endTimeLabel')) as HTMLInputElement).value)
      .toBe('08:00')
    expect((weekdayCheckbox(MONDAY) as HTMLInputElement).checked).toBe(false)
  })

  it('keeps saving disabled while no weekday is selected', async () => {
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())

    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    await user.click(weekdayCheckbox(MONDAY))
    expect((saveButton() as HTMLButtonElement).disabled).toBe(false)
  })

  it('does not offer the active switch while creating a slot', async () => {
    // 新規作成は常に有効なスロットとして作られるため、切り替え自体を出さない。
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())
    expect(isActiveCheckbox()).toBe(null)
  })

  it('creates the slot without an is_active field', async () => {
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())
    await user.type(nameInput(), '昼')
    await user.click(weekdayCheckbox(MONDAY))
    await user.click(weekdayCheckbox(TUESDAY))
    await user.click(saveButton())

    await waitFor(() => expect(createSlot).toHaveBeenCalledOnce())
    expect(createSlot).toHaveBeenCalledWith({
      name: '昼',
      start_time: '07:00',
      end_time: '08:00',
      environment: 'PC',
      weekdays: [MONDAY, TUESDAY],
    })
  })

  it('removes a weekday that is clicked twice', async () => {
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())
    await user.type(nameInput(), '昼')
    await user.click(weekdayCheckbox(MONDAY))
    await user.click(weekdayCheckbox(TUESDAY))
    await user.click(weekdayCheckbox(MONDAY))
    await user.click(saveButton())

    await waitFor(() => expect(createSlot).toHaveBeenCalledOnce())
    expect(createSlot.mock.calls[0][0].weekdays).toEqual([TUESDAY])
  })

  it('closes the form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    await renderList([])
    await user.click(addButton())
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createSlot).not.toHaveBeenCalled()
    expect(screen.queryByLabelText(t('resources.slots.nameLabel'))).toBe(null)
  })
})

describe('SlotList の編集フォーム', () => {
  it('prefills the form from the slot and offers the active switch', async () => {
    const user = userEvent.setup()
    await renderList([makeSlot({ environment: 'MOBILE', is_active: false })])
    await user.click(editButton())

    expect((nameInput() as HTMLInputElement).value).toBe(SLOT_NAME)
    expect((weekdayCheckbox(MONDAY) as HTMLInputElement).checked).toBe(true)
    const activeSwitch = isActiveCheckbox() as HTMLInputElement
    expect(activeSwitch).not.toBe(null)
    expect(activeSwitch.checked).toBe(false)
  })

  it('updates the slot, sending the active switch as well', async () => {
    const user = userEvent.setup()
    await renderList([makeSlot()])
    await user.click(editButton())
    await user.click(isActiveCheckbox() as HTMLElement)
    await user.click(saveButton())

    await waitFor(() => expect(updateSlot).toHaveBeenCalledOnce())
    expect(createSlot).not.toHaveBeenCalled()
    expect(updateSlot).toHaveBeenCalledWith(SLOT_ID, {
      name: SLOT_NAME,
      start_time: '07:00',
      end_time: '08:00',
      environment: 'PC',
      weekdays: [MONDAY],
      is_active: false,
    })
  })

  it('sends the time range the user changed', async () => {
    const user = userEvent.setup()
    await renderList([makeSlot()])
    await user.click(editButton())

    const start = screen.getByLabelText(t('resources.slots.startTimeLabel')) as HTMLInputElement
    const end = screen.getByLabelText(t('resources.slots.endTimeLabel')) as HTMLInputElement
    await user.clear(start)
    await user.type(start, '09:30')
    await user.clear(end)
    await user.type(end, '11:45')
    await user.click(saveButton())

    await waitFor(() => expect(updateSlot).toHaveBeenCalledOnce())
    expect(updateSlot.mock.calls[0][1]).toMatchObject({
      start_time: '09:30',
      end_time: '11:45',
    })
  })

  it('sends the environment the user switched to', async () => {
    const user = userEvent.setup()
    await renderList([makeSlot()])
    await user.click(editButton())
    await user.selectOptions(screen.getByLabelText(t('resources.slots.environmentLabel')), 'MOBILE')
    await user.click(saveButton())

    await waitFor(() => expect(updateSlot).toHaveBeenCalledOnce())
    expect(updateSlot.mock.calls[0][1].environment).toBe('MOBILE')
  })

  it('shows the edit form in place of the slot row', async () => {
    const user = userEvent.setup()
    await renderList([makeSlot()])
    await user.click(editButton())
    expect(screen.queryByText(`${SLOT_NAME} (07:00〜08:00)`)).toBe(null)
  })
})
