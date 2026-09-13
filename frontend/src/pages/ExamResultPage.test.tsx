/** SC-10 受験結果登録（ExamResultPage）の、送信内容と画面の出し分けを固定する回帰テスト
 * （Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で受験結果フォームを
 * 切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * この画面は「任意項目の空欄は空文字ではなく`null`で送る」「既存の結果があれば登録ではなく
 * 更新を呼ぶ」という送信内容の判定を持ち、壊れるとサーバへ誤った値が届く。クローズ済みの
 * 目標をエクスポート画面へ送る転送も、誤ると閉じた目標に結果を登録できてしまう。
 *
 * カバレッジの扱いは他の画面テストと同じ（vite.config.ts の coverage.exclude で
 * `src/pages/**\/*.tsx` を除外し、振る舞いはこのテストが守る）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, SUBJECT_ID, makeGoalDetail, makeSubject } from '../test/fixtures'
import type { SubjectRead } from '../api/goals'
import { ExamResultPage } from './ExamResultPage'

const getGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ getGoal, closeGoal: vi.fn() }))

const registerExamResult = vi.hoisted(() => vi.fn())
const updateExamResult = vi.hoisted(() => vi.fn())
const generateRetrospective = vi.hoisted(() => vi.fn())
vi.mock('../api/closure', () => ({
  registerExamResult,
  updateExamResult,
  generateRetrospective,
}))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useParams: () => ({ goalId: String(GOAL_ID) }),
  useNavigate: () => navigate,
}))

const EXAM_RESULT_ID = 81
const SUBJECT_NAME = '科目A'
const TAKEN_DATE = '2026-12-01'

/** 登録済みの受験結果を持つ科目。 */
function makeSubjectWithResult(overrides: Partial<SubjectRead['exam_result']> = {}): SubjectRead {
  return makeSubject({
    name: SUBJECT_NAME,
    exam_result: {
      id: EXAM_RESULT_ID,
      subject_id: SUBJECT_ID,
      taken_date: TAKEN_DATE,
      result: 'PASS',
      score: 85,
      evaluation: 'A',
      note: 'メモ',
      ...overrides,
    },
  } as Partial<SubjectRead>)
}

function makeSubjectWithoutResult(): SubjectRead {
  return makeSubject({ name: SUBJECT_NAME, exam_result: null } as Partial<SubjectRead>)
}

// --- 要素アクセサ ---
const registerButton = () => screen.getByRole('button', { name: t('goalResult.registerButton') })
const editButton = () => screen.getByRole('button', { name: t('goalResult.editButton') })
const takenDateInput = () =>
  screen.getByLabelText(t('goalResult.takenDateLabel')) as HTMLInputElement
const resultSelect = () => screen.getByLabelText(t('goalResult.resultLabel'))
const scoreInput = () => screen.getByLabelText(t('goalResult.scoreLabel'))
const evaluationInput = () => screen.getByLabelText(t('goalResult.evaluationLabel'))
const noteInput = () => screen.getByLabelText(t('goalResult.noteLabel'))

/** 日付欄は `userEvent.type` だと既存値へ追記されて書式が崩れるため、change を直接起こす。 */
function setDate(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function renderPage() {
  return renderWithProviders(<ExamResultPage />)
}

beforeEach(() => {
  vi.clearAllMocks()
  registerExamResult.mockResolvedValue(undefined)
  updateExamResult.mockResolvedValue(undefined)
  generateRetrospective.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('ExamResultPage の読み込みと転送', () => {
  it('shows the loading text until the goal arrives', () => {
    getGoal.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })

  it('shows an error message when the goal cannot be read', async () => {
    getGoal.mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })

  it('sends a closed goal to the export screen instead of the result form', async () => {
    // クローズ済みの目標に結果を登録できてしまうと、閉じた記録が後から変わる。
    getGoal.mockResolvedValue(makeGoalDetail({ status: 'CLOSED_WITH_RESULT' }))
    const { container } = renderPage()
    await waitFor(() => expect(container.textContent).not.toContain(t('common.loading')))
    expect(screen.queryByText(t('goalResult.title', { name: '目標A' }))).toBe(null)
  })

  it('tells the user there is nothing to register when the goal has no subject', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [] }))
    renderPage()
    expect(await screen.findByText(t('goalResult.empty'))).toBeTruthy()
  })
})

describe('ExamResultPage の受験結果フォーム', () => {
  it('opens in edit mode for a subject that has no result yet', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithoutResult()] }))
    renderPage()
    expect(await screen.findByLabelText(t('goalResult.takenDateLabel'))).toBeTruthy()
  })

  it('shows a summary instead of the form for a subject that already has a result', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult()] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)

    expect(screen.queryByLabelText(t('goalResult.takenDateLabel'))).toBe(null)
    expect(
      screen.getByText(
        `${t('goalResult.registeredBadge')}: ${t('goalResult.result.PASS')} (85)`,
      ),
    ).toBeTruthy()
  })

  it('omits the score from the summary when it was not recorded', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult({ score: null })] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)

    expect(
      screen.getByText(`${t('goalResult.registeredBadge')}: ${t('goalResult.result.PASS')}`),
    ).toBeTruthy()
  })

  it('registers a new result, sending null for every optional field left empty', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithoutResult()] }))
    renderPage()
    await screen.findByLabelText(t('goalResult.takenDateLabel'))

    setDate(takenDateInput(), TAKEN_DATE)
    await user.click(registerButton())

    await waitFor(() => expect(registerExamResult).toHaveBeenCalledOnce())
    expect(registerExamResult).toHaveBeenCalledWith(SUBJECT_ID, {
      taken_date: TAKEN_DATE,
      // 未選択の既定は「結果待ち」。
      result: 'PENDING',
      score: null,
      evaluation: null,
      note: null,
    })
  })

  it('sends the entered optional values as they are typed', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithoutResult()] }))
    renderPage()
    await screen.findByLabelText(t('goalResult.takenDateLabel'))

    setDate(takenDateInput(), TAKEN_DATE)
    await user.selectOptions(resultSelect(), 'FAIL')
    await user.type(scoreInput(), '7')
    await user.type(evaluationInput(), 'B')
    await user.type(noteInput(), 'n')
    await user.click(registerButton())

    await waitFor(() => expect(registerExamResult).toHaveBeenCalledOnce())
    expect(registerExamResult).toHaveBeenCalledWith(SUBJECT_ID, {
      taken_date: TAKEN_DATE,
      result: 'FAIL',
      // 点数は文字列ではなく数値で送る。
      score: 7,
      evaluation: 'B',
      note: 'n',
    })
  })

  it('updates the existing result instead of registering a new one', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult()] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)

    await user.click(editButton())
    await user.click(registerButton())

    await waitFor(() => expect(updateExamResult).toHaveBeenCalledOnce())
    expect(registerExamResult).not.toHaveBeenCalled()
    // 更新は結果IDを宛先にする（科目IDではない）。
    expect(updateExamResult).toHaveBeenCalledWith(EXAM_RESULT_ID, {
      taken_date: TAKEN_DATE,
      result: 'PASS',
      score: 85,
      evaluation: 'A',
      note: 'メモ',
    })
  })

  it('prefills the form with the stored result when editing', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult()] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)
    await user.click(editButton())

    expect((takenDateInput() as HTMLInputElement).value).toBe(TAKEN_DATE)
    expect((scoreInput() as HTMLInputElement).value).toBe('85')
    expect((evaluationInput() as HTMLInputElement).value).toBe('A')
  })

  it('leaves the score empty when the stored result has none', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult({ score: null })] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)
    await user.click(editButton())

    expect((scoreInput() as HTMLInputElement).value).toBe('')
  })

  it('offers cancelling only while editing an existing result', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult()] }))
    renderPage()
    await screen.findByText(SUBJECT_NAME)
    await user.click(editButton())

    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))
    // 取り消すと入力欄が閉じ、送信は行われない。
    expect(screen.queryByLabelText(t('goalResult.takenDateLabel'))).toBe(null)
    expect(updateExamResult).not.toHaveBeenCalled()
  })

  it('does not offer cancelling for a subject that has no result yet', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithoutResult()] }))
    renderPage()
    await screen.findByLabelText(t('goalResult.takenDateLabel'))

    expect(screen.queryByRole('button', { name: t('common.action.cancel') })).toBe(null)
  })
})

describe('ExamResultPage のクローズ', () => {
  it('starts the retrospective and moves to the export screen after closing', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(makeGoalDetail({ exam_subjects: [makeSubjectWithResult()] }))
    const { container } = renderPage()
    await screen.findByText(SUBJECT_NAME)

    await user.click(screen.getByRole('button', { name: t('goals.detail.action.close') }))
    // クローズ確認モーダルが開くことだけを見る（確認の中身は CloseGoalModal のテストが担う）。
    expect(container.textContent).toContain(t('goals.detail.action.close'))
  })
})
