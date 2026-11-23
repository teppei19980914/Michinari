import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleCustomColumnHeaderCell } from './ScheduleCustomColumnHeaderCell'

const onRename = vi.fn()
const onMoveLeft = vi.fn()
const onMoveRight = vi.fn()
const onDelete = vi.fn()

function renderCell(
  overrides: Partial<Parameters<typeof ScheduleCustomColumnHeaderCell>[0]> = {},
) {
  return render(
    <ScheduleCustomColumnHeaderCell
      name="メモ"
      readOnly={false}
      canMoveLeft={true}
      canMoveRight={true}
      hasAnyValue={false}
      onRename={onRename}
      onMoveLeft={onMoveLeft}
      onMoveRight={onMoveRight}
      onDelete={onDelete}
      {...overrides}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ScheduleCustomColumnHeaderCell', () => {
  it('閲覧のみの目標では名前のみ表示し、操作ボタンは出さない', () => {
    renderCell({ readOnly: true })
    expect(screen.getByText('メモ')).not.toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.customColumn.delete') })).toBe(null)
  })

  it('hasErrorのときは入力欄に赤枠のクラスを付ける', () => {
    renderCell({ hasError: true })
    expect(
      (screen.getByLabelText(t('schedule.customColumn.renameLabel')) as HTMLInputElement)
        .className,
    ).toContain('border-danger-text')
  })

  it('名前を変更するとonRenameが呼ばれる', async () => {
    renderCell()
    const input = screen.getByRole('textbox', { name: t('schedule.customColumn.renameLabel') })
    await userEvent.type(input, 'X')
    expect(onRename).toHaveBeenCalled()
  })

  it('左右移動ボタンでonMoveLeft/onMoveRightが呼ばれる', async () => {
    renderCell()
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.customColumn.moveLeft') }),
    )
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.customColumn.moveRight') }),
    )
    expect(onMoveLeft).toHaveBeenCalledTimes(1)
    expect(onMoveRight).toHaveBeenCalledTimes(1)
  })

  it('値が無い列の削除は「空のときの確認」文言を使う', async () => {
    renderCell({ hasAnyValue: false })
    await userEvent.click(screen.getByRole('button', { name: t('schedule.customColumn.delete') }))
    expect(window.confirm).toHaveBeenCalledWith(t('schedule.customColumn.deleteConfirmEmpty'))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('値がある列の削除は「値があるときの確認」文言を使う', async () => {
    renderCell({ hasAnyValue: true })
    await userEvent.click(screen.getByRole('button', { name: t('schedule.customColumn.delete') }))
    expect(window.confirm).toHaveBeenCalledWith(
      t('schedule.customColumn.deleteConfirmWithValue'),
    )
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('削除確認をキャンセルすればonDeleteを呼ばない', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderCell()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.customColumn.delete') }))
    expect(onDelete).not.toHaveBeenCalled()
  })
})
