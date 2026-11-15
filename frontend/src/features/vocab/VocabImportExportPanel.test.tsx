import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabImportExportPanel } from './VocabImportExportPanel'

const previewVocabImport = vi.hoisted(() => vi.fn())
const confirmVocabImport = vi.hoisted(() => vi.fn())
const exportVocabDeck = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ previewVocabImport, confirmVocabImport, exportVocabDeck }))

const downloadBlob = vi.hoisted(() => vi.fn())
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob }))

const DECK_ID = 1
const DECK_NAME = 'デッキA'

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('VocabImportExportPanel の一括登録', () => {
  it('disables the preview button when the textarea is empty', () => {
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)

    expect(
      (screen.getByRole('button', { name: t('vocab.deckDetail.bulkImportPreviewButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('shows the row/error/duplicate counts after previewing', async () => {
    const user = userEvent.setup()
    previewVocabImport.mockResolvedValue({
      rows: [{ line_number: 1, term: '用語', meaning: '意味', aliases: null, note: null }],
      errors: [{ line_number: 2, reason: 'term is empty' }],
      duplicate_count: 1,
    })
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)

    await user.type(screen.getByPlaceholderText(t('vocab.deckDetail.bulkImportPlaceholder')), '用語\t意味')
    await user.click(screen.getByRole('button', { name: t('vocab.deckDetail.bulkImportPreviewButton') }))

    expect(await screen.findByText(/取り込む件数: 1件/)).toBeDefined()
    expect(screen.getByText(/2行目: term is empty/)).toBeDefined()
  })

  it('clears the preview when the text is edited afterwards', async () => {
    const user = userEvent.setup()
    previewVocabImport.mockResolvedValue({
      rows: [{ line_number: 1, term: '用語', meaning: '意味', aliases: null, note: null }],
      errors: [],
      duplicate_count: 0,
    })
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)
    const textarea = screen.getByPlaceholderText(t('vocab.deckDetail.bulkImportPlaceholder'))

    await user.type(textarea, '用語\t意味')
    await user.click(screen.getByRole('button', { name: t('vocab.deckDetail.bulkImportPreviewButton') }))
    await screen.findByText(/取り込む件数: 1件/)
    await user.type(textarea, '2')

    expect(screen.queryByText(/取り込む件数: 1件/)).toBeNull()
  })

  it('disables the confirm button when there are no importable rows', async () => {
    const user = userEvent.setup()
    previewVocabImport.mockResolvedValue({ rows: [], errors: [], duplicate_count: 0 })
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)

    await user.type(screen.getByPlaceholderText(t('vocab.deckDetail.bulkImportPlaceholder')), 'x')
    await user.click(screen.getByRole('button', { name: t('vocab.deckDetail.bulkImportPreviewButton') }))

    expect(
      (
        await screen.findByRole('button', { name: t('vocab.deckDetail.bulkImportConfirmButton') })
      ).hasAttribute('disabled'),
    ).toBe(true)
  })

  it('confirms with the mapped rows and clears the form on success', async () => {
    const user = userEvent.setup()
    previewVocabImport.mockResolvedValue({
      rows: [{ line_number: 1, term: '用語', meaning: '意味', aliases: '別名', note: '補足' }],
      errors: [],
      duplicate_count: 0,
    })
    confirmVocabImport.mockResolvedValue({ created_count: 1 })
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)

    await user.type(screen.getByPlaceholderText(t('vocab.deckDetail.bulkImportPlaceholder')), '用語\t意味')
    await user.click(screen.getByRole('button', { name: t('vocab.deckDetail.bulkImportPreviewButton') }))
    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.bulkImportConfirmButton') }))

    await waitFor(() =>
      expect(confirmVocabImport).toHaveBeenCalledWith(DECK_ID, [
        { term: '用語', meaning: '意味', aliases: '別名', note: '補足' },
      ]),
    )
    await waitFor(() =>
      expect(screen.queryByText(/取り込む件数/)).toBeNull(),
    )
  })
})

describe('VocabImportExportPanel の書き出し', () => {
  it('downloads the exported text with the deck name as filename', async () => {
    const user = userEvent.setup()
    exportVocabDeck.mockResolvedValue({ text: '用語\t意味\n' })
    renderWithProviders(<VocabImportExportPanel deckId={DECK_ID} deckName={DECK_NAME} />)

    await user.click(screen.getByRole('button', { name: t('vocab.deckDetail.exportButton') }))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledOnce())
    expect(downloadBlob.mock.calls[0][1]).toBe(`${DECK_NAME}.tsv`)
    const blob = downloadBlob.mock.calls[0][0] as Blob
    expect(await blob.text()).toBe('用語\t意味\n')
  })
})
