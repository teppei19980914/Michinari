import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleEmptyState } from './ScheduleEmptyState'

const onAddRow = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleEmptyState', () => {
  it('案内文と行を追加ボタンを表示する', () => {
    render(<ScheduleEmptyState readOnly={false} onAddRow={onAddRow} />)
    expect(screen.getByText(t('schedule.empty.title'))).not.toBe(null)
    expect(screen.getByRole('button', { name: t('schedule.toolbar.addRow') })).not.toBe(null)
  })

  it('ボタンを押すとonAddRowが呼ばれる', async () => {
    render(<ScheduleEmptyState readOnly={false} onAddRow={onAddRow} />)
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.addRow') }))
    expect(onAddRow).toHaveBeenCalledTimes(1)
  })

  it('閲覧のみの目標では行を追加ボタンを表示しない', () => {
    render(<ScheduleEmptyState readOnly={true} onAddRow={onAddRow} />)
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.addRow') })).toBe(null)
  })
})
