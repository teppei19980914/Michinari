import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ScheduleConflictDialog } from './ScheduleConflictDialog'

const onReload = vi.fn()
const onKeepEditing = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleConflictDialog', () => {
  it('open=falseのときは何も表示しない', () => {
    renderWithProviders(
      <ScheduleConflictDialog open={false} onReload={onReload} onKeepEditing={onKeepEditing} />,
    )
    expect(screen.queryByText(t('schedule.conflict.title'))).toBe(null)
  })

  it('open=trueのとき、メッセージと2つの選択肢を表示する', () => {
    renderWithProviders(
      <ScheduleConflictDialog open={true} onReload={onReload} onKeepEditing={onKeepEditing} />,
    )
    expect(screen.getByText(t('schedule.conflict.title'))).not.toBe(null)
    expect(screen.getByText(t('errors.SCHEDULE_REVISION_CONFLICT'))).not.toBe(null)
  })

  it('「最新を読み込む」を押すとonReloadが呼ばれる', async () => {
    renderWithProviders(
      <ScheduleConflictDialog open={true} onReload={onReload} onKeepEditing={onKeepEditing} />,
    )
    await userEvent.click(screen.getByRole('button', { name: t('schedule.conflict.reload') }))
    expect(onReload).toHaveBeenCalledTimes(1)
    expect(onKeepEditing).not.toHaveBeenCalled()
  })

  it('「編集を続ける」を押すとonKeepEditingが呼ばれる', async () => {
    renderWithProviders(
      <ScheduleConflictDialog open={true} onReload={onReload} onKeepEditing={onKeepEditing} />,
    )
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.conflict.keepEditing') }),
    )
    expect(onKeepEditing).toHaveBeenCalledTimes(1)
    expect(onReload).not.toHaveBeenCalled()
  })

  it('右上の閉じるボタンもonKeepEditingと同じ扱いにする', async () => {
    renderWithProviders(
      <ScheduleConflictDialog open={true} onReload={onReload} onKeepEditing={onKeepEditing} />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'close' }))
    expect(onKeepEditing).toHaveBeenCalledTimes(1)
  })
})
