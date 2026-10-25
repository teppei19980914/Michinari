/** 添付ファイルの複数選択UI（開発Todo_添付ファイル機能_v1.0 A1）の描画テスト。
 *
 * 選択状態はこのコンポーネントが保持せず、呼び出し側のstateをそのまま表示・更新する
 * （controlled component）ため、`useAttachments`を差し替えて一覧のみ用意し、
 * チェックボックスの操作で`onChange`が正しい配列を受け取ることを確認する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AttachmentPicker } from './AttachmentPicker'

const useAttachments = vi.hoisted(() => vi.fn())
vi.mock('./useAttachment', () => ({ useAttachments }))

const ATTACHMENTS = [
  { id: 1, file_name: 'a.pdf', char_count: 100 },
  { id: 2, file_name: 'b.pdf', char_count: 200 },
]

beforeEach(() => {
  useAttachments.mockReturnValue({ data: ATTACHMENTS })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AttachmentPicker', () => {
  it('registered attachments がない場合は空の案内文を表示する', () => {
    useAttachments.mockReturnValue({ data: [] })
    renderWithProviders(<AttachmentPicker selectedIds={[]} onChange={vi.fn()} />)

    expect(screen.getByText(t('attachment.picker.none'))).toBeTruthy()
  })

  it('一覧をチェックボックスで表示する', () => {
    renderWithProviders(<AttachmentPicker selectedIds={[]} onChange={vi.fn()} />)

    expect(screen.getByText('a.pdf')).toBeTruthy()
    expect(screen.getByText('b.pdf')).toBeTruthy()
    expect(screen.queryByText(t('attachment.picker.selectedTotalChars', { count: 0 }))).toBeNull()
  })

  it('未選択のチェックボックスをクリックすると選択に追加する', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(<AttachmentPicker selectedIds={[]} onChange={onChange} />)

    await user.click(screen.getByLabelText(/a\.pdf/))

    expect(onChange).toHaveBeenCalledWith([1])
  })

  it('選択済みのチェックボックスをクリックすると選択から外す', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(<AttachmentPicker selectedIds={[1, 2]} onChange={onChange} />)

    await user.click(screen.getByLabelText(/a\.pdf/))

    expect(onChange).toHaveBeenCalledWith([2])
  })

  it('選択中は合計文字数を表示する', () => {
    renderWithProviders(<AttachmentPicker selectedIds={[1, 2]} onChange={vi.fn()} />)

    expect(
      screen.getByText(t('attachment.picker.selectedTotalChars', { count: 300 })),
    ).toBeTruthy()
  })
})
