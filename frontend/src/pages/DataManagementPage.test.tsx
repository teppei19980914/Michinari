/** SC-12 データ管理（DataManagementPage）の操作と取り消せない操作のガードを固定する
 * 回帰テスト（Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応でバックアップ一覧を
 * 切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * インポートと復元は既存データを置き換える取り消せない操作であり、確認ダイアログを
 * 素通りさせるとその場で全データが失われる。選んだファイルの取り扱い（同じファイルを
 * 選び直せるよう入力欄を毎回空にする）も、壊れると2回目以降が無反応になり気づきにくい。
 *
 * カバレッジの扱いは他の画面テストと同じ（vite.config.ts の coverage.exclude で
 * `src/pages/**\/*.tsx` を除外し、振る舞いはこのテストが守る）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { formatBytes } from '../features/data/formatBytes'
import type { BackupRead } from '../api/data'
import { DataManagementPage } from './DataManagementPage'

const listBackups = vi.hoisted(() => vi.fn())
const createBackup = vi.hoisted(() => vi.fn())
const restoreBackup = vi.hoisted(() => vi.fn())
const downloadExportFile = vi.hoisted(() => vi.fn())
const importDataFile = vi.hoisted(() => vi.fn())
vi.mock('../api/data', () => ({
  listBackups,
  createBackup,
  restoreBackup,
  downloadExportFile,
  importDataFile,
}))

const downloadBlob = vi.hoisted(() => vi.fn())
vi.mock('../utils/downloadBlob', () => ({ downloadBlob }))

const BACKUP_ID = 'backup-20260913'
const BACKUP_SIZE_BYTES = 2_097_152

function makeBackup(overrides: Partial<BackupRead> = {}): BackupRead {
  return {
    id: BACKUP_ID,
    created_at: '2026-09-13T09:00:00',
    size_bytes: BACKUP_SIZE_BYTES,
    ...overrides,
  }
}

// --- 要素アクセサ ---
const exportButton = () => screen.getByRole('button', { name: t('dataManagement.export') })
const importButton = () => screen.getByRole('button', { name: t('dataManagement.import') })
const backupButton = () => screen.getByRole('button', { name: t('dataManagement.backup') })
const restoreButton = () =>
  screen.getByRole('button', { name: t('dataManagement.backups.restore') })
/** ファイル入力欄は視覚的に隠してあり、role でもラベルでも引けないため要素から直接取る。 */
const fileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement

async function renderPage(backups: BackupRead[] = []) {
  listBackups.mockResolvedValue(backups)
  const result = renderWithProviders(<DataManagementPage />)
  await screen.findByText(t('dataManagement.title'))
  if (backups.length === 0) {
    await screen.findByText(t('dataManagement.backups.empty'))
  } else {
    await screen.findByText(new RegExp(t('dataManagement.backups.sizeLabel')))
  }
  return result
}

/** `window.location.reload` はjsdomでは呼べないため差し替える。 */
function stubReload() {
  const reload = vi.fn()
  vi.stubGlobal('location', { ...window.location, reload })
  return reload
}

beforeEach(() => {
  vi.clearAllMocks()
  createBackup.mockResolvedValue(makeBackup())
  restoreBackup.mockResolvedValue(undefined)
  downloadExportFile.mockResolvedValue(new Blob(['{}']))
  importDataFile.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('DataManagementPage のバックアップ一覧', () => {
  it('tells the user there is no backup yet', async () => {
    await renderPage([])
    expect(screen.getByText(t('dataManagement.backups.empty'))).toBeTruthy()
  })

  it('shows the creation time and the human readable size of each backup', async () => {
    await renderPage([makeBackup()])
    expect(
      screen.getByText(
        new RegExp(`${t('dataManagement.backups.sizeLabel')}: ${formatBytes(BACKUP_SIZE_BYTES)}`),
      ),
    ).toBeTruthy()
    expect(
      screen.getByText(new RegExp(t('dataManagement.backups.createdAtLabel'))),
    ).toBeTruthy()
  })

  it('shows the loading text until the backup list arrives', () => {
    listBackups.mockReturnValue(new Promise(() => undefined))
    renderWithProviders(<DataManagementPage />)
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })
})

describe('DataManagementPage のエクスポート', () => {
  it('downloads the exported data under a fixed file name', async () => {
    const user = userEvent.setup()
    await renderPage([])
    await user.click(exportButton())

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledOnce())
    expect(downloadBlob.mock.calls[0][1]).toBe('michinari_export.json')
  })
})

/** ミューテーションは同期的には走らないため、送信の有無を見る前に一度待つ。
 * 待たずに `not.toHaveBeenCalled()` を見ると、確認を素通りする不具合でも通ってしまう。 */
async function flushMutations() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

function selectFile(container: HTMLElement, files: File[]) {
  fireEvent.change(fileInput(container), { target: { files } })
}

const JSON_FILE = () => new File(['{}'], 'data.json', { type: 'application/json' })

describe('DataManagementPage のインポート', () => {
  it('does not import when the confirmation is dismissed', async () => {
    const confirmSpy = vi.fn(() => false)
    vi.stubGlobal('confirm', confirmSpy)
    const { container } = await renderPage([])
    selectFile(container, [JSON_FILE()])

    expect(confirmSpy).toHaveBeenCalledOnce()
    await flushMutations()
    expect(importDataFile).not.toHaveBeenCalled()
  })

  it('imports only after the confirmation is accepted, then reloads', async () => {
    const reload = stubReload()
    vi.stubGlobal('confirm', vi.fn(() => true))
    const { container } = await renderPage([])
    const file = JSON_FILE()
    selectFile(container, [file])

    await waitFor(() => expect(importDataFile).toHaveBeenCalledWith(file))
    await waitFor(() => expect(reload).toHaveBeenCalledOnce())
  })

  it('does nothing when the file dialog is dismissed without a file', async () => {
    const confirmSpy = vi.fn(() => true)
    vi.stubGlobal('confirm', confirmSpy)
    const { container } = await renderPage([])
    selectFile(container, [])

    // ファイルが無ければ確認すら出さない。
    expect(confirmSpy).not.toHaveBeenCalled()
    await flushMutations()
    expect(importDataFile).not.toHaveBeenCalled()
  })

  it('clears the file input so the same file can be picked again', async () => {
    // ブラウザは同じファイルを選び直しても、値が残っていると change を発火しない。
    // jsdom の file input は value を読むと常に空文字を返すため、代入そのものを観測する。
    vi.stubGlobal('confirm', vi.fn(() => false))
    const { container } = await renderPage([])
    const input = fileInput(container)
    const setValue = vi.fn()
    Object.defineProperty(input, 'value', { set: setValue, get: () => '', configurable: true })

    fireEvent.change(input, { target: { files: [JSON_FILE()] } })
    expect(setValue).toHaveBeenCalledWith('')
  })

  it('opens the file dialog from the import button', async () => {
    const user = userEvent.setup()
    const { container } = await renderPage([])
    const click = vi.spyOn(fileInput(container), 'click')
    await user.click(importButton())

    expect(click).toHaveBeenCalledOnce()
  })
})

describe('DataManagementPage のバックアップ作成と復元', () => {
  it('creates a backup and refreshes the list', async () => {
    const user = userEvent.setup()
    await renderPage([])
    await user.click(backupButton())

    await waitFor(() => expect(createBackup).toHaveBeenCalledOnce())
    // 作成後は一覧を取り直す（初回＋再取得で2回）。
    await waitFor(() => expect(listBackups.mock.calls.length).toBeGreaterThan(1))
  })

  it('does not restore when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => false))
    await renderPage([makeBackup()])
    await user.click(restoreButton())

    await flushMutations()
    expect(restoreBackup).not.toHaveBeenCalled()
  })

  it('restores only after the confirmation is accepted, then reloads', async () => {
    const user = userEvent.setup()
    const reload = stubReload()
    vi.stubGlobal('confirm', vi.fn(() => true))
    await renderPage([makeBackup()])
    await user.click(restoreButton())

    await waitFor(() => expect(restoreBackup).toHaveBeenCalledWith(BACKUP_ID))
    await waitFor(() => expect(reload).toHaveBeenCalledOnce())
  })
})
