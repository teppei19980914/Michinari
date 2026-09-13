/** 教材タブの「押した結果どう送信されるか」と、取り消しできない操作のガードを固定する（Phase 35）。
 *
 * この画面は送信内容を決める判定を `.tsx` 内に持っている（手動締切が off のときは入力済みの
 * 日付があっても `due_date` を送らない、所要ブロック時間は空欄なら `null` にする、教材の有無で
 * 作成と更新を呼び分ける）。いずれも 2026-09-13 のカバレッジ監査時点で未検証であり、
 * 壊れるとサーバへ誤った値が送られる。削除は取り消せないため、確認ダイアログのガードも固定する。
 *
 * 締切の自動導出そのものは `materialDueDate.test.ts` が担うため、ここでは扱わない。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, MATERIAL_ID, SUBJECT_ID, makeGoalDetail, makeMaterial } from '../../test/fixtures'
import { MaterialsTab } from './MaterialsTab'

// 実通信はしない。判定は各 .ts のテストが担うため、ここでは「何が送信されたか」を見る。
const createMaterial = vi.hoisted(() => vi.fn())
const updateMaterial = vi.hoisted(() => vi.fn())
const deleteMaterial = vi.hoisted(() => vi.fn())
const deactivateMaterial = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({
  createMaterial,
  updateMaterial,
  deleteMaterial,
  deactivateMaterial,
}))

const SUBJECT_NAME = '科目A'
/** 科目Aの受験日（fixtures の既定値）。締切の自動導出はこの前日になる。 */
const AUTO_DUE_DATE = '2026-11-30'
/** 自動導出の締切より前の開始日。開始日は必須項目のため、入れないと送信自体が行われない。 */
const START_DATE = '2026-09-01'

// --- 要素アクセサ（同じクエリを各テストへ散らさないため先頭へ集約する） ---
const addButton = () => screen.getByRole('button', { name: t('goals.materials.addTitle') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const deleteButton = () => screen.getByRole('button', { name: t('common.action.delete') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const deactivateButton = () => screen.getByRole('button', { name: t('goals.materials.deactivate') })
const subjectCheckbox = () => screen.getByRole('checkbox', { name: SUBJECT_NAME })
/** 選択欄は「必要な環境」「品質指標」の2つ。ラベル要素の中身が入れ子で
 *  getByLabelText では一意に決まらないため、出現順で選ぶ（0=必要な環境、1=品質指標）。 */
const selects = () => screen.getAllByRole('combobox')
/** 手動締切のチェックボックス。ラベル要素が日付入力欄も包んでいるため、名前の部分一致で選ぶ。 */
const manualDueDateCheckbox = () =>
  screen.getByRole('checkbox', {
    name: (accessibleName: string) =>
      accessibleName.includes(t('goals.materials.dueDateManualLabel')),
  })
/** 日付入力欄は開始日・締切の2つ。同じラベル配下に複数の入力があり getByLabelText では
 *  一意に決まらないため、種別と出現順で選ぶ（0=開始日、1=締切）。 */
const dateInputs = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]'))

/** 日付欄へ値を入れる。
 *
 * `userEvent.type` は既存の値へ追記するため、日付欄では書式が崩れて空値になる。
 * 制御されたinputに対しては change を直接起こすほうが確実なので、こちらを使う。 */
function setDate(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } })
}

/** 教材の新規追加フォームを開き、保存できる最低限の入力を済ませる。 */
async function openAddFormWithValidInput(user: ReturnType<typeof userEvent.setup>) {
  await user.click(addButton())
  await user.type(screen.getByLabelText(t('goals.materials.nameLabel')), '新しい教材')
  await user.type(screen.getByLabelText(t('goals.materials.unitLabel')), '問')
  await user.clear(screen.getByLabelText(t('goals.materials.totalAmountLabel')))
  await user.type(screen.getByLabelText(t('goals.materials.totalAmountLabel')), '50')
  await user.click(subjectCheckbox())
  setDate(screen.getByLabelText<HTMLInputElement>(t('goals.materials.startDateLabel')), START_DATE)
}

beforeEach(() => {
  vi.clearAllMocks()
  createMaterial.mockResolvedValue(makeMaterial())
  updateMaterial.mockResolvedValue(makeMaterial())
  deleteMaterial.mockResolvedValue(undefined)
  deactivateMaterial.mockResolvedValue(makeMaterial({ is_active: false }))
  // 教材ごとの時間枠チェック（SlotCheckWarning）。既定では「足りている」＝警告なし。
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ sufficient: true }),
      } as unknown as Response),
    ),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('MaterialsTab の一覧', () => {
  it('shows the empty message when the goal has no material', () => {
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    expect(screen.getByText(t('goals.materials.empty'))).toBeDefined()
  })

  it('hides every editing action when read only', () => {
    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly />,
    )

    expect(screen.queryByRole('button', { name: t('common.action.edit') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('common.action.delete') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.materials.addTitle') })).toBeNull()
  })

  it('hides the deactivate action for a material that is already inactive', () => {
    renderWithProviders(
      <MaterialsTab
        goal={makeGoalDetail({ materials: [makeMaterial({ is_active: false })] })}
        readOnly={false}
      />,
    )

    expect(screen.queryByRole('button', { name: t('goals.materials.deactivate') })).toBeNull()
  })

  it('warns when the slot check reports the material does not fit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ sufficient: false }),
        } as unknown as Response),
      ),
    )

    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly={false} />,
    )

    expect(
      await screen.findByText(t('goals.materials.slotInsufficientWarning')),
    ).toBeDefined()
  })
})

describe('MaterialsTab の取り消せない操作', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly={false} />,
    )

    await user.click(deleteButton())

    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(deleteMaterial).not.toHaveBeenCalled()
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly={false} />,
    )

    await user.click(deleteButton())

    await waitFor(() => expect(deleteMaterial).toHaveBeenCalledWith(MATERIAL_ID))
  })

  it('deactivates without asking for a confirmation', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly={false} />,
    )

    await user.click(deactivateButton())

    await waitFor(() => expect(deactivateMaterial).toHaveBeenCalledWith(MATERIAL_ID))
  })
})

describe('MaterialsTab の送信内容', () => {
  it('creates a material and sends null for the untouched optional values', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    await openAddFormWithValidInput(user)
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    expect(createMaterial).toHaveBeenCalledWith(GOAL_ID, {
      name: '新しい教材',
      unit_label: '問',
      total_amount: 50,
      planned_cycles: 1,
      subject_ids: [SUBJECT_ID],
      start_date: START_DATE,
      due_date_is_manual: false,
      // 自動導出のときは締切を送らない（サーバ側が決める）。
      due_date: null,
      // 空欄は 0 ではなく null。
      required_block_minutes: null,
      required_environment: 'ANY',
      quality_metric_type: 'NONE',
    })
  })

  it('sends the typed due date only while the manual switch is on', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <MaterialsTab goal={makeGoalDetail()} readOnly={false} />,
    )

    await openAddFormWithValidInput(user)
    await user.click(manualDueDateCheckbox())
    setDate(dateInputs(container)[1], '2026-10-15')
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    expect(createMaterial.mock.calls[0][1]).toMatchObject({
      due_date_is_manual: true,
      due_date: '2026-10-15',
    })
  })

  it('drops the typed due date when the manual switch is turned back off', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <MaterialsTab goal={makeGoalDetail()} readOnly={false} />,
    )

    await openAddFormWithValidInput(user)
    await user.click(manualDueDateCheckbox())
    setDate(dateInputs(container)[1], '2026-10-15')
    await user.click(manualDueDateCheckbox())
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    // 入力欄には日付が残っているが、自動導出へ戻した以上は送ってはいけない。
    expect(createMaterial.mock.calls[0][1]).toMatchObject({
      due_date_is_manual: false,
      due_date: null,
    })
  })

  it('sends the entered block minutes as a number', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    await openAddFormWithValidInput(user)
    await user.type(
      screen.getByLabelText(t('goals.materials.requiredBlockMinutesLabel')),
      '45',
    )
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    expect(createMaterial.mock.calls[0][1]).toMatchObject({ required_block_minutes: 45 })
  })

  it('sends null when the manual switch is on but no date was entered', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    await openAddFormWithValidInput(user)
    await user.click(manualDueDateCheckbox())
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    // 空文字をそのまま送ると日付として解釈できずサーバ側で弾かれる。
    expect(createMaterial.mock.calls[0][1]).toMatchObject({
      due_date_is_manual: true,
      due_date: null,
    })
  })

  it('sends the planned cycles, environment and quality metric as entered', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    await openAddFormWithValidInput(user)
    await user.clear(screen.getByLabelText(t('goals.materials.plannedCyclesLabel')))
    await user.type(screen.getByLabelText(t('goals.materials.plannedCyclesLabel')), '3')
    await user.selectOptions(selects()[0], 'PC')
    await user.selectOptions(selects()[1], 'SELF_SCORED')
    await user.click(saveButton())

    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce())
    expect(createMaterial.mock.calls[0][1]).toMatchObject({
      planned_cycles: 3,
      required_environment: 'PC',
      quality_metric_type: 'SELF_SCORED',
    })
  })

  it('updates the existing material instead of creating a new one', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <MaterialsTab goal={makeGoalDetail({ materials: [makeMaterial()] })} readOnly={false} />,
    )

    await user.click(editButton())
    await user.click(saveButton())

    await waitFor(() => expect(updateMaterial).toHaveBeenCalledOnce())
    expect(updateMaterial.mock.calls[0][0]).toBe(MATERIAL_ID)
    expect(createMaterial).not.toHaveBeenCalled()
  })

  it('prefills the block minutes when the material already has one', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <MaterialsTab
        goal={makeGoalDetail({ materials: [makeMaterial({ required_block_minutes: 30 })] })}
        readOnly={false}
      />,
    )

    await user.click(editButton())

    // 未設定（null）と 0分 を取り違えないよう、値がある場合は文字列として入力欄へ出す。
    expect(
      screen.getByLabelText<HTMLInputElement>(t('goals.materials.requiredBlockMinutesLabel')).value,
    ).toBe('30')

    await user.click(saveButton())

    await waitFor(() => expect(updateMaterial).toHaveBeenCalledOnce())
    expect(updateMaterial.mock.calls[0][1]).toMatchObject({ required_block_minutes: 30 })
  })
})

describe('MaterialsTab の入力チェック', () => {
  it('blocks saving while the start date is after the due date', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <MaterialsTab goal={makeGoalDetail()} readOnly={false} />,
    )

    await openAddFormWithValidInput(user)
    // 締切（自動導出＝科目Aの受験日の前日）より後の開始日へ入れ替える。
    setDate(dateInputs(container)[0], '2026-12-31')

    expect(
      screen.getByText(t('goals.materials.startDateAfterDueDateError', { dueDate: AUTO_DUE_DATE })),
    ).toBeDefined()
    expect(saveButton().hasAttribute('disabled')).toBe(true)
  })

  it('keeps saving disabled while no subject is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaterialsTab goal={makeGoalDetail()} readOnly={false} />)

    await user.click(addButton())

    expect(saveButton().hasAttribute('disabled')).toBe(true)

    await user.click(subjectCheckbox())

    expect(saveButton().hasAttribute('disabled')).toBe(false)

    // 選択を外すと未選択へ戻る（選択の解除が積み増しになっていないことの確認）。
    await user.click(subjectCheckbox())

    expect(saveButton().hasAttribute('disabled')).toBe(true)
  })
})
