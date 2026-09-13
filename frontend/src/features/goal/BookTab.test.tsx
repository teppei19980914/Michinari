/** 書籍タブの「押した結果どう送信されるか」と、読了という取り消せない操作を固定する（Phase 35）。
 *
 * 読書目標は1目標1冊で、書籍の未登録／登録済み／編集中で表示が切り替わる。読了は目標のクローズを
 * 伴い取り消せないため、確認ダイアログを経ること・読了レポートの生成失敗が遷移を妨げないことを固定する
 * （後者は仕様書6.9の方針であり、壊れると読了できたのに画面が進まない状態になる）。
 *
 * 書名初期値の決定（`resolveInitialBookTitle`）は `bookTitle.test.ts` が担う。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { BOOK_ID, GOAL_ID, makeBook, makeGoalDetail } from '../../test/fixtures'
import { BookTab } from './BookTab'

const createBook = vi.hoisted(() => vi.fn())
const updateBook = vi.hoisted(() => vi.fn())
const completeBook = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ createBook, updateBook, completeBook }))

const generateRetrospective = vi.hoisted(() => vi.fn())
vi.mock('../../api/closure', () => ({ generateRetrospective }))

// 遷移先を確かめるため useNavigate だけ差し替える（MemoryRouter はそのまま使う）。
const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const completeButton = () => screen.getByRole('button', { name: t('goals.book.completeButton') })
const confirmButton = () => screen.getByRole('button', { name: t('common.action.confirm') })
const cancelButton = () => screen.getByRole('button', { name: t('common.action.cancel') })
const dateInputs = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]'))

function setDate(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } })
}

/** 書籍未登録の読書目標。 */
const goalWithoutBook = () => makeGoalDetail({ category: 'READING', name: '書籍の目標名' })
/** 書籍登録済みの読書目標。 */
const goalWithBook = (bookOverrides = {}, goalOverrides = {}) =>
  makeGoalDetail({ category: 'READING', book: makeBook(bookOverrides), ...goalOverrides })

beforeEach(() => {
  vi.clearAllMocks()
  createBook.mockResolvedValue(makeBook())
  updateBook.mockResolvedValue(makeBook())
  completeBook.mockResolvedValue(undefined)
  generateRetrospective.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('BookTab の表示', () => {
  it('shows the empty message when there is no book and the goal is read only', () => {
    renderWithProviders(<BookTab goal={goalWithoutBook()} readOnly />)

    expect(screen.getByText(t('goals.book.empty'))).toBeDefined()
  })

  it('offers the registration form when there is no book yet', () => {
    renderWithProviders(<BookTab goal={goalWithoutBook()} readOnly={false} />)

    // 書名の初期値には目標名を転記する（二重入力を避けるため）。
    expect(screen.getByLabelText<HTMLInputElement>(t('goals.book.titleLabel')).value).toBe(
      '書籍の目標名',
    )
    // 登録前は取りやめる先がないためキャンセルは出さない。
    expect(screen.queryByRole('button', { name: t('common.action.cancel') })).toBeNull()
  })

  it('hides the author line when the book has none', () => {
    const { unmount } = renderWithProviders(<BookTab goal={goalWithBook()} readOnly />)
    expect(screen.getByText('著者A')).toBeDefined()

    unmount()
    renderWithProviders(<BookTab goal={goalWithBook({ author: null })} readOnly />)

    expect(screen.queryByText('著者A')).toBeNull()
  })

  it('falls back when the book has never been read', () => {
    renderWithProviders(<BookTab goal={goalWithBook({ last_reading_date: null })} readOnly />)

    expect(screen.getByText(t('goals.book.lastReadingDateUnavailable'))).toBeDefined()
  })

  it('shows the progress only once a current page exists', () => {
    const { unmount } = renderWithProviders(<BookTab goal={goalWithBook()} readOnly />)
    expect(screen.getByText(t('goals.book.progressLabel'))).toBeDefined()

    unmount()
    renderWithProviders(
      <BookTab goal={goalWithBook({ current_page: null, progress_rate: null })} readOnly />,
    )

    expect(screen.queryByText(t('goals.book.progressLabel'))).toBeNull()
  })

  it('hides every action when read only', () => {
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly />)

    expect(screen.queryByRole('button', { name: t('common.action.edit') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.book.completeButton') })).toBeNull()
  })

  it('offers finishing the book only while the goal is active', () => {
    const { unmount } = renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)
    expect(completeButton()).toBeDefined()

    unmount()
    renderWithProviders(
      <BookTab goal={goalWithBook({}, { status: 'PAUSED' })} readOnly={false} />,
    )

    expect(screen.queryByRole('button', { name: t('goals.book.completeButton') })).toBeNull()
  })
})

describe('BookTab の送信内容', () => {
  it('creates the book and sends null for an empty author', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <BookTab goal={goalWithoutBook()} readOnly={false} />,
    )

    await user.type(screen.getByLabelText(t('goals.book.totalPagesLabel')), '250')
    setDate(dateInputs(container)[0], '2026-09-01')
    setDate(dateInputs(container)[1], '2026-11-30')
    await user.click(saveButton())

    await waitFor(() => expect(createBook).toHaveBeenCalledOnce())
    expect(createBook).toHaveBeenCalledWith(GOAL_ID, {
      title: '書籍の目標名',
      // 空欄は空文字ではなく未設定として送る。
      author: null,
      total_pages: 250,
      start_date: '2026-09-01',
      due_date: '2026-11-30',
    })
  })

  it('sends the title the user typed over the transcribed goal name', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <BookTab goal={goalWithoutBook()} readOnly={false} />,
    )

    // 目標名からの転記はあくまで初期値で、以降は利用者の編集を優先する。
    await user.clear(screen.getByLabelText(t('goals.book.titleLabel')))
    await user.type(screen.getByLabelText(t('goals.book.titleLabel')), '実際の書名')
    await user.type(screen.getByLabelText(t('goals.book.totalPagesLabel')), '250')
    setDate(dateInputs(container)[0], '2026-09-01')
    setDate(dateInputs(container)[1], '2026-11-30')
    await user.click(saveButton())

    await waitFor(() => expect(createBook).toHaveBeenCalledOnce())
    expect(createBook.mock.calls[0][1]).toMatchObject({ title: '実際の書名' })
  })

  it('keeps the author when it is entered', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <BookTab goal={goalWithoutBook()} readOnly={false} />,
    )

    await user.type(screen.getByLabelText(t('goals.book.authorLabel')), '著者B')
    await user.type(screen.getByLabelText(t('goals.book.totalPagesLabel')), '250')
    setDate(dateInputs(container)[0], '2026-09-01')
    setDate(dateInputs(container)[1], '2026-11-30')
    await user.click(saveButton())

    await waitFor(() => expect(createBook).toHaveBeenCalledOnce())
    expect(createBook.mock.calls[0][1]).toMatchObject({ author: '著者B' })
  })

  it('updates the existing book instead of creating a new one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)

    await user.click(editButton())
    await user.click(saveButton())

    await waitFor(() => expect(updateBook).toHaveBeenCalledOnce())
    expect(updateBook.mock.calls[0][0]).toBe(BOOK_ID)
    expect(createBook).not.toHaveBeenCalled()
  })

  it('leaves the edit form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)

    await user.click(editButton())
    await user.click(cancelButton())

    expect(updateBook).not.toHaveBeenCalled()
    expect(editButton()).toBeDefined()
  })
})

describe('BookTab の読了', () => {
  it('does not finish the book until the dialog is confirmed', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)

    await user.click(completeButton())
    await user.click(cancelButton())

    expect(completeBook).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('finishes the book, requests the report and moves to the export screen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)

    await user.click(completeButton())
    await user.click(confirmButton())

    await waitFor(() => expect(completeBook).toHaveBeenCalledWith(BOOK_ID))
    expect(generateRetrospective).toHaveBeenCalledWith(GOAL_ID, false)
    expect(navigate).toHaveBeenCalledWith(ROUTES.goalExport(GOAL_ID))
  })

  it('still moves to the export screen when generating the report fails', async () => {
    const user = userEvent.setup()
    // 読了レポートの生成失敗を読了処理の失敗として扱わない（仕様書6.9）。
    generateRetrospective.mockRejectedValue(new Error('report failed'))
    renderWithProviders(<BookTab goal={goalWithBook()} readOnly={false} />)

    await user.click(completeButton())
    await user.click(confirmButton())

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(ROUTES.goalExport(GOAL_ID)))
  })
})
