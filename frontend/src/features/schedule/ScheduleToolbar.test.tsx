import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleToolbar, type ScheduleToolbarProps } from './ScheduleToolbar'

const onChangeFrozenRowCount = vi.fn()
const onChangeFrozenColumnCount = vi.fn()
const onGoToToday = vi.fn()
const onAddRow = vi.fn()
const onAddColumn = vi.fn()
const onDiscard = vi.fn()
const onSave = vi.fn()

function renderToolbar(overrides: Partial<ScheduleToolbarProps> = {}) {
  return render(
    <ScheduleToolbar
      readOnly={false}
      frozenRowCount={0}
      frozenColumnCount={1}
      maxFrozenRowCount={5}
      maxFrozenColumnCount={7}
      canAddRow={true}
      canAddColumn={true}
      hasUnsavedChanges={false}
      isSaving={false}
      maxItems={100}
      maxCustomColumns={10}
      onChangeFrozenRowCount={onChangeFrozenRowCount}
      onChangeFrozenColumnCount={onChangeFrozenColumnCount}
      onGoToToday={onGoToToday}
      onAddRow={onAddRow}
      onAddColumn={onAddColumn}
      onDiscard={onDiscard}
      onSave={onSave}
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

describe('ScheduleToolbar', () => {
  it('今日へ・行を追加・列を追加ボタンが動く', async () => {
    renderToolbar()
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.goToToday') }))
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.addRow') }))
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.addColumn') }))
    expect(onGoToToday).toHaveBeenCalledTimes(1)
    expect(onAddRow).toHaveBeenCalledTimes(1)
    expect(onAddColumn).toHaveBeenCalledTimes(1)
  })

  it('上限に達しているときは追加ボタンを無効化し、上限の案内を表示する', () => {
    renderToolbar({ canAddRow: false, canAddColumn: false })
    expect(
      (screen.getByRole('button', { name: t('schedule.toolbar.addRow') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(screen.getByText(t('schedule.toolbar.rowLimitReached', { max: 100 }))).not.toBe(null)
    expect(screen.getByText(t('schedule.toolbar.columnLimitReached', { max: 10 }))).not.toBe(null)
  })

  it('未保存の変更が無ければ保存・破棄ボタンは無効', () => {
    renderToolbar({ hasUnsavedChanges: false })
    expect(
      (screen.getByRole('button', { name: t('schedule.toolbar.save') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(
      (
        screen.getByRole('button', {
          name: t('schedule.toolbar.discardChanges'),
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true)
  })

  it('未保存の変更があれば保存ボタンでonSaveが呼ばれる', async () => {
    renderToolbar({ hasUnsavedChanges: true })
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.save') }))
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('破棄は確認のうえonDiscardを呼ぶ', async () => {
    renderToolbar({ hasUnsavedChanges: true })
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.toolbar.discardChanges') }),
    )
    expect(window.confirm).toHaveBeenCalledWith(t('schedule.toolbar.discardConfirm'))
    expect(onDiscard).toHaveBeenCalledTimes(1)
  })

  it('破棄確認でキャンセルした場合はonDiscardを呼ばない', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderToolbar({ hasUnsavedChanges: true })
    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.toolbar.discardChanges') }),
    )
    expect(onDiscard).not.toHaveBeenCalled()
  })

  it('閲覧のみの目標では追加・保存・破棄ボタンを表示しない', () => {
    renderToolbar({ readOnly: true })
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.addRow') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.save') })).toBe(null)
  })

  it('固定行数・固定列数を変更するとそれぞれのハンドラが呼ばれる', async () => {
    renderToolbar()
    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenRowsLabel'), { exact: false }),
      '2',
    )
    expect(onChangeFrozenRowCount).toHaveBeenCalledWith(2)

    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenColumnsLabel'), { exact: false }),
      '3',
    )
    expect(onChangeFrozenColumnCount).toHaveBeenCalledWith(3)
  })
})
