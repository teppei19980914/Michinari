import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleStatusSelect } from './ScheduleStatusSelect'

const onChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleStatusSelect', () => {
  it('現在の状況を選択済みで表示する', () => {
    render(<ScheduleStatusSelect value="IN_PROGRESS" disabled={false} onChange={onChange} />)
    const select = screen.getByRole('combobox', {
      name: t('schedule.columns.status'),
    }) as HTMLSelectElement
    expect(select.value).toBe('IN_PROGRESS')
  })

  it('選択を変えるとonChangeへ新しい値を渡す', async () => {
    render(<ScheduleStatusSelect value="NOT_STARTED" disabled={false} onChange={onChange} />)
    const select = screen.getByRole('combobox', { name: t('schedule.columns.status') })
    await userEvent.selectOptions(select, t('schedule.status.DONE'))
    expect(onChange).toHaveBeenCalledWith('DONE')
  })

  it('readOnlyの目標ではdisabledになる', () => {
    render(<ScheduleStatusSelect value="NOT_STARTED" disabled={true} onChange={onChange} />)
    const select = screen.getByRole('combobox', {
      name: t('schedule.columns.status'),
    }) as HTMLSelectElement
    expect(select.disabled).toBe(true)
  })

  it('hasErrorのときは赤枠のクラスを付ける', () => {
    render(
      <ScheduleStatusSelect value="NOT_STARTED" disabled={false} hasError={true} onChange={onChange} />,
    )
    const select = screen.getByRole('combobox', {
      name: t('schedule.columns.status'),
    }) as HTMLSelectElement
    expect(select.className).toContain('border-danger-text')
  })
})
