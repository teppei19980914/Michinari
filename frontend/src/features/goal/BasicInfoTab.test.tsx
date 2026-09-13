/** 基本情報タブの送信内容と、目標種別による表示の切り替えを固定する（Phase 35）。
 *
 * 種別ごとの見出し語の決定（`resolveByGoalCategory`）は `goalCategoryVariant.test.ts` が担うため、
 * ここでは種別に応じた見出しが実際に表示へ届いていることだけを確かめる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail } from '../../test/fixtures'
import { BasicInfoTab } from './BasicInfoTab'

const updateGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ updateGoal }))

const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const startDateInput = () =>
  screen.getByLabelText<HTMLInputElement>(t('goals.basicInfo.startDateLabel'))
const memoInput = () => screen.getByLabelText<HTMLTextAreaElement>(t('goals.basicInfo.memoLabel'))

beforeEach(() => {
  vi.clearAllMocks()
  updateGoal.mockResolvedValue(makeGoalDetail())
})

afterEach(() => {
  cleanup()
})

describe('BasicInfoTab の表示', () => {
  it('prefills the stored values', () => {
    renderWithProviders(
      <BasicInfoTab goal={makeGoalDetail({ memo: 'メモ本文' })} readOnly={false} />,
    )

    expect(
      screen.getByLabelText<HTMLInputElement>(t('goals.basicInfo.nameLabel')).value,
    ).toBe('目標A')
    expect(startDateInput().value).toBe('2026-09-01')
    expect(memoInput().value).toBe('メモ本文')
  })

  it('starts the memo empty when the goal has none', () => {
    renderWithProviders(<BasicInfoTab goal={makeGoalDetail()} readOnly={false} />)

    expect(memoInput().value).toBe('')
  })

  it.each([
    ['EXAM', 'goals.basicInfo.nameLabel'],
    ['READING', 'goals.basicInfo.nameLabelReading'],
    ['WORK', 'goals.basicInfo.nameLabelWork'],
  ] as const)('labels the name field for %s goals', (category, localeKey) => {
    renderWithProviders(<BasicInfoTab goal={makeGoalDetail({ category })} readOnly={false} />)

    expect(screen.getByLabelText(t(localeKey))).toBeDefined()
  })

  it('disables every field and hides saving when read only', () => {
    renderWithProviders(<BasicInfoTab goal={makeGoalDetail()} readOnly />)

    expect(
      screen.getByLabelText<HTMLInputElement>(t('goals.basicInfo.nameLabel')).disabled,
    ).toBe(true)
    expect(startDateInput().disabled).toBe(true)
    expect(memoInput().disabled).toBe(true)
    expect(screen.queryByRole('button', { name: t('common.action.save') })).toBeNull()
  })
})

describe('BasicInfoTab の送信内容', () => {
  it('sends the edited values and reports success', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BasicInfoTab goal={makeGoalDetail()} readOnly={false} />)

    await user.clear(screen.getByLabelText(t('goals.basicInfo.nameLabel')))
    await user.type(screen.getByLabelText(t('goals.basicInfo.nameLabel')), '新しい目標名')
    await user.type(memoInput(), '追記したメモ')
    await user.click(saveButton())

    await waitFor(() => expect(updateGoal).toHaveBeenCalledOnce())
    expect(updateGoal).toHaveBeenCalledWith(GOAL_ID, {
      name: '新しい目標名',
      start_date: '2026-09-01',
      memo: '追記したメモ',
    })
    expect(await screen.findByText(t('common.saveSucceeded'))).toBeDefined()
  })

  it('sends the edited start date', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BasicInfoTab goal={makeGoalDetail()} readOnly={false} />)

    // 開始日は日次ノルマの起点になるため、書き換えがそのまま送られることを確かめる。
    fireEvent.change(startDateInput(), { target: { value: '2026-08-15' } })
    await user.click(saveButton())

    await waitFor(() => expect(updateGoal).toHaveBeenCalledOnce())
    expect(updateGoal.mock.calls[0][1]).toMatchObject({ start_date: '2026-08-15' })
  })
})
