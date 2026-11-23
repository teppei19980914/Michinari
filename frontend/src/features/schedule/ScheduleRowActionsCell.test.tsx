import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleRowActionsCell } from './ScheduleRowActionsCell'

const onMoveUp = vi.fn()
const onMoveDown = vi.fn()
const onInsertBelow = vi.fn()
const onDelete = vi.fn()

function renderCell(overrides: Partial<Parameters<typeof ScheduleRowActionsCell>[0]> = {}) {
  return render(
    <ScheduleRowActionsCell
      readOnly={false}
      canMoveUp={true}
      canMoveDown={true}
      onMoveUp={onMoveUp}
      onMoveDown={onMoveDown}
      onInsertBelow={onInsertBelow}
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

describe('ScheduleRowActionsCell', () => {
  it('閲覧のみの目標では何も表示しない', () => {
    const { container } = renderCell({ readOnly: true })
    expect(container.firstChild).toBe(null)
  })

  it('上へ・下へを押すと対応するハンドラが呼ばれる', async () => {
    renderCell()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.rowActions.moveUp') }))
    await userEvent.click(screen.getByRole('button', { name: t('schedule.rowActions.moveDown') }))
    expect(onMoveUp).toHaveBeenCalledTimes(1)
    expect(onMoveDown).toHaveBeenCalledTimes(1)
  })

  it('先頭行では上へが無効、末尾行では下へが無効になる', () => {
    renderCell({ canMoveUp: false, canMoveDown: false })
    const upButton = screen.getByRole('button', {
      name: t('schedule.rowActions.moveUp'),
    }) as HTMLButtonElement
    const downButton = screen.getByRole('button', {
      name: t('schedule.rowActions.moveDown'),
    }) as HTMLButtonElement
    expect(upButton.disabled).toBe(true)
    expect(downButton.disabled).toBe(true)
  })

  it('下に挿入を押すとonInsertBelowが呼ばれる', async () => {
    renderCell()
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.rowActions.insertBelow') }),
    )
    expect(onInsertBelow).toHaveBeenCalledTimes(1)
  })

  it('削除は確認のうえonDeleteを呼ぶ', async () => {
    renderCell()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.rowActions.delete') }))
    expect(window.confirm).toHaveBeenCalledWith(t('schedule.rowActions.deleteConfirm'))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('削除確認でキャンセルした場合はonDeleteを呼ばない', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderCell()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.rowActions.delete') }))
    expect(onDelete).not.toHaveBeenCalled()
  })
})
