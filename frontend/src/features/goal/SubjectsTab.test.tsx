/** 試験科目タブの「押した結果どう送信されるか」と、取り消しできない操作のガードを固定する（Phase 35）。
 *
 * この画面は受験日の種別（期間／確定日）によって送信する項目を切り替える判定を `.tsx` 内に持ち、
 * 使わない側を必ず `null` で送る。取り違えるとサーバ側に矛盾した受験日が保存される。
 * 科目の削除と日程の確定はどちらも取り消せないため、ガードと送信値を固定する。
 *
 * 合格点の組み立て（`buildPassingScorePayload`）と表示（`formatPassingScoreDisplay`）、
 * 期間開始日の過去判定（`isSubjectRangeStartInPast`）は、それぞれ
 * `passingScore.test.ts` / `subjectWarnings.test.ts` が担うため、ここでは結線だけを見る。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, SUBJECT_ID, makeGoalDetail, makeSubject } from '../../test/fixtures'
import { SubjectsTab } from './SubjectsTab'

const createSubject = vi.hoisted(() => vi.fn())
const updateSubject = vi.hoisted(() => vi.fn())
const deleteSubject = vi.hoisted(() => vi.fn())
const fixSubjectDate = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({
  createSubject,
  updateSubject,
  deleteSubject,
  fixSubjectDate,
}))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../../api/records', () => ({ getToday }))

const TODAY = '2026-09-13'
const RANGE_FROM = '2026-10-01'
const RANGE_TO = '2026-10-31'

/** 受験日が期間の科目。日程確定・過去警告の分岐で使う。 */
const rangeSubject = (overrides = {}) =>
  makeSubject({
    exam_date_type: 'RANGE',
    exam_date_from: RANGE_FROM,
    exam_date_to: RANGE_TO,
    exam_date_fixed: null,
    ...overrides,
  })

const addButton = () => screen.getByRole('button', { name: t('goals.subjects.addTitle') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const deleteButton = () => screen.getByRole('button', { name: t('common.action.delete') })
const fixDateButton = () => screen.getByRole('button', { name: t('goals.subjects.fixDate') })
const confirmButton = () => screen.getByRole('button', { name: t('common.action.confirm') })
/** 選択欄は「受験日の種別」「合格点の種別」の2つ。ラベルが入れ子で一意に決まらないため出現順で選ぶ。 */
const selects = () => screen.getAllByRole('combobox')
const dateInputs = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]'))

/** `userEvent.type` は日付欄で書式が崩れるため、change を直接起こす（MaterialsTab.test.tsx と同じ）。 */
function setDate(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } })
}

beforeEach(() => {
  vi.clearAllMocks()
  createSubject.mockResolvedValue(makeSubject())
  updateSubject.mockResolvedValue(makeSubject())
  deleteSubject.mockResolvedValue(undefined)
  fixSubjectDate.mockResolvedValue(makeSubject())
  getToday.mockResolvedValue({ logical_date: TODAY })
})

afterEach(() => {
  cleanup()
})

describe('SubjectsTab の一覧', () => {
  it('shows the empty message when the goal has no subject', () => {
    renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    expect(screen.getByText(t('goals.subjects.empty'))).toBeDefined()
  })

  it('hides every editing action when read only', () => {
    renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly />)

    expect(screen.queryByRole('button', { name: t('common.action.edit') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('common.action.delete') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.subjects.addTitle') })).toBeNull()
  })

  it('offers fixing the date only while the exam date is a range', () => {
    const { unmount } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [rangeSubject()] })} readOnly={false} />,
    )
    expect(fixDateButton()).toBeDefined()

    unmount()
    renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly={false} />)

    expect(screen.queryByRole('button', { name: t('goals.subjects.fixDate') })).toBeNull()
  })

  it('falls back to a dash for the dates that are not set', () => {
    renderWithProviders(
      <SubjectsTab
        goal={makeGoalDetail({
          exam_subjects: [
            rangeSubject({ exam_date_from: null, exam_date_to: null }),
            makeSubject({ id: SUBJECT_ID + 1, exam_date_fixed: null }),
          ],
        })}
        readOnly
      />,
    )

    expect(screen.getByText(/- 〜 -/)).toBeDefined()
  })

  it('shows the passing score only when it is set', () => {
    const { unmount } = renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly />)
    expect(screen.queryByText(new RegExp(t('goals.subjects.passingScoreResultLabel')))).toBeNull()

    unmount()
    renderWithProviders(
      <SubjectsTab
        goal={makeGoalDetail({ exam_subjects: [makeSubject({ passing_score: 70 })] })}
        readOnly
      />,
    )

    expect(
      screen.getByText(new RegExp(t('goals.subjects.passingScoreResultLabel'))),
    ).toBeDefined()
  })

  it('warns only when the range already started', async () => {
    const { unmount } = renderWithProviders(
      <SubjectsTab
        goal={makeGoalDetail({ exam_subjects: [rangeSubject({ exam_date_from: '2026-09-01' })] })}
        readOnly
      />,
    )
    expect(await screen.findByText(t('goals.subjects.pastRangeWarning'))).toBeDefined()

    unmount()
    renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [rangeSubject()] })} readOnly />,
    )

    await waitFor(() => expect(getToday).toHaveBeenCalled())
    expect(screen.queryByText(t('goals.subjects.pastRangeWarning'))).toBeNull()
  })
})

describe('SubjectsTab の取り消せない操作', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly={false} />)

    await user.click(deleteButton())

    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(deleteSubject).not.toHaveBeenCalled()
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly={false} />)

    await user.click(deleteButton())

    await waitFor(() => expect(deleteSubject).toHaveBeenCalledWith(SUBJECT_ID))
  })

  it('prefills the fix date dialog with the start of the range and sends the confirmed date', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [rangeSubject()] })} readOnly={false} />,
    )

    await user.click(fixDateButton())

    // 期間の開始日を初期値に置く（利用者が最も選びがちな日付のため）。
    const dialogDate = dateInputs(container).at(-1) as HTMLInputElement
    expect(dialogDate.value).toBe(RANGE_FROM)

    setDate(dialogDate, '2026-10-20')
    await user.click(confirmButton())

    await waitFor(() => expect(fixSubjectDate).toHaveBeenCalledWith(SUBJECT_ID, '2026-10-20'))
  })

  it('closes the fix date dialog without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [rangeSubject()] })} readOnly={false} />,
    )

    await user.click(fixDateButton())
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(fixSubjectDate).not.toHaveBeenCalled()
    expect(screen.queryByText(t('goals.subjects.fixDateConfirm.body'))).toBeNull()
  })

  it('starts the fix date dialog empty when the range has no start', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab
        goal={makeGoalDetail({ exam_subjects: [rangeSubject({ exam_date_from: null })] })}
        readOnly={false}
      />,
    )

    await user.click(fixDateButton())

    expect((dateInputs(container).at(-1) as HTMLInputElement).value).toBe('')
  })
})

describe('SubjectsTab の送信内容', () => {
  it('sends only the range dates and nulls the fixed date', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    setDate(dateInputs(container)[0], RANGE_FROM)
    setDate(dateInputs(container)[1], RANGE_TO)
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject).toHaveBeenCalledWith(GOAL_ID, {
      name: '科目B',
      exam_date_type: 'RANGE',
      exam_date_from: RANGE_FROM,
      exam_date_to: RANGE_TO,
      exam_date_fixed: null,
      passing_score: null,
      passing_score_type: 'PERCENTAGE',
      passing_score_max: null,
    })
  })

  it('sends only the fixed date and nulls the range', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    await user.selectOptions(selects()[0], 'FIXED')
    setDate(dateInputs(container)[0], '2026-12-01')
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      exam_date_type: 'FIXED',
      exam_date_from: null,
      exam_date_to: null,
      exam_date_fixed: '2026-12-01',
    })
  })

  it('drops the fixed date that was typed before switching back to a range', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    // いったん確定日で入力してから期間へ戻す。
    await user.selectOptions(selects()[0], 'FIXED')
    setDate(dateInputs(container)[0], '2026-12-01')
    await user.selectOptions(selects()[0], 'RANGE')
    setDate(dateInputs(container)[0], RANGE_FROM)
    setDate(dateInputs(container)[1], RANGE_TO)
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    // 入力欄には確定日が残っているが、期間へ戻した以上は送ってはいけない
    // （送るとサーバ側で期間と確定日の両方を持つ矛盾した科目になる）。
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      exam_date_type: 'RANGE',
      exam_date_from: RANGE_FROM,
      exam_date_to: RANGE_TO,
      exam_date_fixed: null,
    })
  })

  it('drops the range dates that were typed before switching to a fixed date', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    setDate(dateInputs(container)[0], RANGE_FROM)
    setDate(dateInputs(container)[1], RANGE_TO)
    await user.selectOptions(selects()[0], 'FIXED')
    setDate(dateInputs(container)[0], '2026-12-01')
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      exam_date_type: 'FIXED',
      exam_date_from: null,
      exam_date_to: null,
      exam_date_fixed: '2026-12-01',
    })
  })

  it('nulls the unentered range dates instead of sending empty strings', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    // 日付欄は required だが、送信経路そのものを直接起こして空値の扱いを確かめる。
    fireEvent.submit(screen.getByRole('button', { name: t('common.action.save') }).closest('form')!)

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      exam_date_from: null,
      exam_date_to: null,
      exam_date_fixed: null,
    })
  })

  it('switches the passing score inputs and sends the raw score pair', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    setDate(dateInputs(container)[0], RANGE_FROM)
    setDate(dateInputs(container)[1], RANGE_TO)
    await user.selectOptions(selects()[1], 'RAW_SCORE')
    await user.type(screen.getByLabelText(t('goals.subjects.passingScoreRawLabel')), '70')
    await user.type(screen.getByLabelText(t('goals.subjects.passingScoreMaxLabel')), '100')
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      passing_score: 70,
      passing_score_type: 'RAW_SCORE',
      passing_score_max: 100,
    })
  })

  it('sends the percentage passing score', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.type(screen.getByLabelText(t('goals.subjects.nameLabel')), '科目B')
    setDate(dateInputs(container)[0], RANGE_FROM)
    setDate(dateInputs(container)[1], RANGE_TO)
    await user.type(screen.getByLabelText(t('goals.subjects.passingScoreLabel')), '60')
    await user.click(saveButton())

    await waitFor(() => expect(createSubject).toHaveBeenCalledOnce())
    expect(createSubject.mock.calls[0][1]).toMatchObject({
      passing_score: 60,
      passing_score_type: 'PERCENTAGE',
      passing_score_max: null,
    })
  })

  it('updates the existing subject instead of creating a new one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SubjectsTab goal={makeGoalDetail()} readOnly={false} />)

    await user.click(editButton())
    await user.click(saveButton())

    await waitFor(() => expect(updateSubject).toHaveBeenCalledOnce())
    expect(updateSubject.mock.calls[0][0]).toBe(SUBJECT_ID)
    expect(createSubject).not.toHaveBeenCalled()
  })

  it('closes the form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SubjectsTab goal={makeGoalDetail({ exam_subjects: [] })} readOnly={false} />,
    )

    await user.click(addButton())
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createSubject).not.toHaveBeenCalled()
    expect(addButton()).toBeDefined()
  })
})
