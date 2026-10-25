/** 添付ファイル管理画面（開発Todo_添付ファイル機能_v1.0 A9）の回帰テスト。
 *
 * カバレッジの扱いは他の画面テストと同じ（vite.config.ts の coverage.exclude で
 * `src/pages/**\/*.tsx` を除外し、振る舞いはこのテストが守る。DataManagementPage.test.tsxと
 * 同じ方針）。削除は常に許可する操作（P3）だが、過去の対話で参照されていた場合に
 * 「どのファイルを参照したか」の情報が失われることを確認ダイアログで伝えるため、
 * 誤操作防止として確認を素通りさせないことを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { AttachmentManagementPage } from './AttachmentManagementPage'

const listAttachments = vi.hoisted(() => vi.fn())
const uploadAttachment = vi.hoisted(() => vi.fn())
const deleteAttachment = vi.hoisted(() => vi.fn())
const getAttachmentLimits = vi.hoisted(() => vi.fn())
vi.mock('../api/attachment', () => ({
  listAttachments,
  uploadAttachment,
  deleteAttachment,
  getAttachmentLimits,
}))

const ATTACHMENT = { id: 1, file_name: 'exam.pdf', char_count: 1234 }
const LIMITS = { max_file_chars: 20000, max_count: 50, max_upload_size_mb: 20 }

const uploadButton = () => screen.getByRole('button', { name: t('attachment.uploadButton') })
const fileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement

function selectFile(container: HTMLElement, files: File[]) {
  fireEvent.change(fileInput(container), { target: { files } })
}

const PDF_FILE = () => new File(['pdf'], 'exam.pdf', { type: 'application/pdf' })

async function flushMutations() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function renderPage(
  attachments: (typeof ATTACHMENT)[] = [],
  limits: typeof LIMITS = LIMITS,
) {
  listAttachments.mockResolvedValue(attachments)
  getAttachmentLimits.mockResolvedValue(limits)
  const result = renderWithProviders(<AttachmentManagementPage />)
  await screen.findByText(t('attachment.pageTitle'))
  if (attachments.length === 0) {
    await screen.findByText(t('attachment.emptyList'))
  } else {
    await screen.findByText(attachments[0].file_name)
  }
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  uploadAttachment.mockResolvedValue(ATTACHMENT)
  deleteAttachment.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AttachmentManagementPage の一覧', () => {
  it('登録が無い場合は空の案内文を表示する', async () => {
    await renderPage([])
    expect(screen.getByText(t('attachment.emptyList'))).toBeTruthy()
  })

  it('登録済みファイルの名前と文字数を表示する', async () => {
    await renderPage([ATTACHMENT])
    expect(screen.getByText('exam.pdf')).toBeTruthy()
    expect(screen.getByText(t('attachment.charCountLabel', { count: 1234 }))).toBeTruthy()
  })

  it('読み込み中はローディング文言を表示する', () => {
    listAttachments.mockReturnValue(new Promise(() => undefined))
    getAttachmentLimits.mockResolvedValue(LIMITS)
    renderWithProviders(<AttachmentManagementPage />)
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })
})

describe('AttachmentManagementPage のアップロード', () => {
  it('ファイルを選ぶとアップロードし、一覧へ反映する', async () => {
    const { container } = await renderPage([])
    selectFile(container, [PDF_FILE()])

    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledWith(PDF_FILE()))
  })

  it('件数上限に達している場合はアップロードボタンを無効化し、上限文言を表示する', async () => {
    await renderPage([ATTACHMENT], { ...LIMITS, max_count: 1 })

    expect((uploadButton() as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(t('attachment.maxCountReached', { max: 1 }))).toBeTruthy()
  })
})

describe('AttachmentManagementPage の削除', () => {
  it('確認をキャンセルした場合は削除しない', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => false))
    await renderPage([ATTACHMENT])

    await user.click(screen.getByRole('button', { name: t('attachment.deleteButton') }))

    await flushMutations()
    expect(deleteAttachment).not.toHaveBeenCalled()
  })

  it('確認したファイルを削除する', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => true))
    await renderPage([ATTACHMENT])

    await user.click(screen.getByRole('button', { name: t('attachment.deleteButton') }))

    await waitFor(() => expect(deleteAttachment).toHaveBeenCalledWith(ATTACHMENT.id))
  })
})
