/** 実績入力欄（SC-06 日次報告・SC-07 進捗のみ登録で共用）の見え方と、入力が呼び出し元へ
 * どう伝わるかを固定する回帰テスト（Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で教材カードを切り出す
 * にあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * この部品は品質指標の方式で入力欄の形が3通りに変わり、複数目標の教材が1つの一覧に
 * 混ざる。取り違えても「何かの入力欄が並んでいる」状態になり、画面を見ても気づけない。
 *
 * 判定そのものは qualityInput.test.ts・groupByGoal.test.ts が担うため、ここでは
 * 「画面に何が出るか」「どの教材の変更として通知されるか」に絞る。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import { t } from '../../locales/t'
import type { QuotaItemRead } from '../../api/records'
import type { StudyLogFormValue } from './studyLogForm'
import { StudyLogFields } from './StudyLogFields'

const GOAL_A = { id: 1, name: '目標A' }
const GOAL_B = { id: 2, name: '目標B' }
const MATERIAL_A_ID = 11
const MATERIAL_B_ID = 12
const SLOT_ID = 51
const SLOT_NAME = '朝の枠'
const OTHER_SLOT_ID = 52
const OTHER_SLOT_NAME = '夜の枠'

function makeQuotaItem(overrides: Partial<QuotaItemRead> = {}): QuotaItemRead {
  return {
    material_id: MATERIAL_A_ID,
    material_name: '教材A',
    unit_label: '問',
    current_cycle: 1,
    planned_cycles: 3,
    daily_quota: 12.34,
    quality_metric_type: 'NONE',
    goal_id: GOAL_A.id,
    goal_name: GOAL_A.name,
    slot_defaults: [{ slot_id: SLOT_ID, slot_name: SLOT_NAME, minutes: 30 }],
    ...overrides,
  }
}

function makeValue(overrides: Partial<StudyLogFormValue> = {}): StudyLogFormValue {
  return { slotMinutes: {}, amountCompleted: '', cycleNumber: '', qualityValue: '', ...overrides }
}

const SLOT_NAMES = new Map([
  [SLOT_ID, SLOT_NAME],
  [OTHER_SLOT_ID, OTHER_SLOT_NAME],
])

const onChangeField = vi.fn()
const onChangeSlotMinutes = vi.fn()

function renderFields({
  quotaItems = [makeQuotaItem()],
  values = { [MATERIAL_A_ID]: makeValue() } as Record<number, StudyLogFormValue>,
  showMinutesOptionalNotice = false,
} = {}) {
  return renderWithProviders(
    <StudyLogFields
      quotaItems={quotaItems}
      values={values}
      onChangeField={onChangeField}
      onChangeSlotMinutes={onChangeSlotMinutes}
      slotNames={SLOT_NAMES}
      showMinutesOptionalNotice={showMinutesOptionalNotice}
    />,
  )
}

/** 完了分量の入力欄。単位がラベルに埋め込まれるため、教材の単位から組み立てて引く。 */
const amountInput = (unitLabel = '問') =>
  screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: unitLabel }))
const cycleInput = () => screen.getByLabelText(t('dailyReport.studyLog.cycleNumberLabel'))

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('StudyLogFields', () => {
  it('tells the user there is nothing to record when no material is due', () => {
    renderFields({ quotaItems: [] })
    expect(screen.getByText(t('dailyReport.studyLog.empty'))).toBeTruthy()
  })

  it('shows the material name, the cycle and the rounded daily quota', () => {
    renderFields()
    expect(screen.getByText('教材A')).toBeTruthy()
    expect(
      screen.getByText(t('dailyReport.studyLog.cycleLabel', { current: 1, planned: 3 })),
    ).toBeTruthy()
    // ノルマは小数第1位までに丸めて出す（12.34 → 12.3）。
    expect(
      screen.getByText(t('dailyReport.studyLog.quotaLabel', { quota: 12.3, unit: '問' })),
    ).toBeTruthy()
  })

  it('skips a material that has no form value yet', () => {
    // 値が未初期化の教材を描画すると入力欄が非制御になるため、カードごと出さない。
    renderFields({ values: {} })
    expect(screen.queryByText('教材A')).toBe(null)
  })

  it('reports the typed amount for the material it belongs to', async () => {
    const user = userEvent.setup()
    renderFields()
    await user.type(amountInput(), '7')
    expect(onChangeField).toHaveBeenCalledWith(MATERIAL_A_ID, 'amountCompleted', '7')
  })

  it('reports the typed cycle number for the material it belongs to', async () => {
    const user = userEvent.setup()
    renderFields()
    await user.type(cycleInput(), '2')
    expect(onChangeField).toHaveBeenCalledWith(MATERIAL_A_ID, 'cycleNumber', '2')
  })

  it('hides the quality input when the material has no quality metric', () => {
    renderFields()
    expect(
      screen.queryByLabelText(t('dailyReport.studyLog.qualityShortLabel.PERCENT')),
    ).toBe(null)
    expect(
      screen.queryByLabelText(t('dailyReport.studyLog.qualityShortLabel.SUBJECTIVE_SCALE')),
    ).toBe(null)
  })

  it('offers a percentage input for an objective quality metric', async () => {
    const user = userEvent.setup()
    renderFields({ quotaItems: [makeQuotaItem({ quality_metric_type: 'OBJECTIVE' })] })
    const input = screen.getByLabelText(t('dailyReport.studyLog.qualityShortLabel.PERCENT'))
    expect(input.getAttribute('type')).toBe('number')
    expect(input.getAttribute('max')).toBe('100')
    await user.type(input, '8')
    expect(onChangeField).toHaveBeenCalledWith(MATERIAL_A_ID, 'qualityValue', '8')
  })

  it('offers the five-step scale for a subjective quality metric', async () => {
    const user = userEvent.setup()
    renderFields({ quotaItems: [makeQuotaItem({ quality_metric_type: 'SUBJECTIVE' })] })
    const select = screen.getByLabelText(
      t('dailyReport.studyLog.qualityShortLabel.SUBJECTIVE_SCALE'),
    )
    // 未選択の選択肢＋1〜5の5段階（時間枠の追加用セレクトと混ざらないよう選択欄内で数える）。
    expect(within(select).getAllByRole('option').length).toBe(6)
    expect(within(select).getByText(t('dailyReport.studyLog.qualityUnselected'))).toBeTruthy()
    await user.selectOptions(select, '4')
    expect(onChangeField).toHaveBeenCalledWith(MATERIAL_A_ID, 'qualityValue', '4')
  })

  it('reports the slot minutes merged into the existing ones of that material', async () => {
    const user = userEvent.setup()
    renderFields({
      values: { [MATERIAL_A_ID]: makeValue({ slotMinutes: { [OTHER_SLOT_ID]: '15' } }) },
    })
    await user.type(screen.getByLabelText(new RegExp(SLOT_NAME)), '5')
    // 他の枠の入力を落とさずに、触った枠だけを差し替えて通知する。
    expect(onChangeSlotMinutes).toHaveBeenCalledWith(MATERIAL_A_ID, {
      [OTHER_SLOT_ID]: '15',
      [SLOT_ID]: '5',
    })
  })

  it('adds an empty entry for the slot the user picked', async () => {
    const user = userEvent.setup()
    renderFields()
    await user.selectOptions(
      screen.getByLabelText(t('dailyReport.studyLog.addSlotLabel')),
      String(OTHER_SLOT_ID),
    )
    expect(onChangeSlotMinutes).toHaveBeenCalledWith(MATERIAL_A_ID, { [OTHER_SLOT_ID]: '' })
  })

  it('does not head the list with a goal name while every material shares one goal', () => {
    renderFields()
    expect(screen.queryByRole('heading', { name: GOAL_A.name })).toBe(null)
  })

  it('heads each group with its goal name once two goals are mixed', () => {
    renderFields({
      quotaItems: [
        makeQuotaItem(),
        makeQuotaItem({
          material_id: MATERIAL_B_ID,
          material_name: '教材B',
          goal_id: GOAL_B.id,
          goal_name: GOAL_B.name,
        }),
      ],
      values: { [MATERIAL_A_ID]: makeValue(), [MATERIAL_B_ID]: makeValue() },
    })
    expect(screen.getByRole('heading', { name: GOAL_A.name })).toBeTruthy()
    expect(screen.getByRole('heading', { name: GOAL_B.name })).toBeTruthy()
  })

  it('reports the change against the material the input belongs to when goals are mixed', async () => {
    const user = userEvent.setup()
    renderFields({
      quotaItems: [
        makeQuotaItem(),
        makeQuotaItem({
          material_id: MATERIAL_B_ID,
          material_name: '教材B',
          unit_label: '頁',
          goal_id: GOAL_B.id,
          goal_name: GOAL_B.name,
        }),
      ],
      values: { [MATERIAL_A_ID]: makeValue(), [MATERIAL_B_ID]: makeValue() },
    })
    await user.type(amountInput('頁'), '3')
    expect(onChangeField).toHaveBeenCalledWith(MATERIAL_B_ID, 'amountCompleted', '3')
  })

  it('notes that the minutes are optional only when the caller asks for it', () => {
    // SC-07（進捗のみ登録）専用の案内。SC-06 では出さない。
    renderFields()
    expect(screen.queryByText(t('progressOnly.minutesOptionalNotice'))).toBe(null)
    cleanup()
    renderFields({ showMinutesOptionalNotice: true })
    expect(screen.getByText(t('progressOnly.minutesOptionalNotice'))).toBeTruthy()
  })
})
