import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../../locales/t'
import type { SlotAllocationFormValues } from '../slotAllocationForm'
import { Step4TimeSlots } from './Step4TimeSlots'

const NO_ROWS_PROPS = {
  rows: [],
  values: {},
  onChangeMinutes: vi.fn(),
  weekdayHours: '',
  weekendHours: '',
  onChangeWeekdayHours: vi.fn(),
  onChangeWeekendHours: vi.fn(),
}

describe('Step4TimeSlots（スロット未設定）', () => {
  it('reports the weekday and weekend hour inputs', async () => {
    const user = userEvent.setup()
    const onChangeWeekdayHours = vi.fn()
    const onChangeWeekendHours = vi.fn()
    render(
      <Step4TimeSlots
        {...NO_ROWS_PROPS}
        onChangeWeekdayHours={onChangeWeekdayHours}
        onChangeWeekendHours={onChangeWeekendHours}
      />,
    )

    await user.type(screen.getByLabelText(t('goals.examWizard.step4.weekdayHoursLabel')), '2')
    await user.type(screen.getByLabelText(t('goals.examWizard.step4.weekendHoursLabel')), '3')

    expect(onChangeWeekdayHours).toHaveBeenCalledWith('2')
    expect(onChangeWeekendHours).toHaveBeenCalledWith('3')
  })

  it('shows both previews once both hours are entered', () => {
    render(<Step4TimeSlots {...NO_ROWS_PROPS} weekdayHours="2" weekendHours="3" />)

    expect(screen.getByText(t('goals.examWizard.step4.weekdayPreview', { start: '20:00', end: '22:00' }))).toBeDefined()
    expect(screen.getByText(t('goals.examWizard.step4.weekendPreview', { start: '09:00', end: '12:00' }))).toBeDefined()
  })

  it('hides both previews while hours are 0', () => {
    render(<Step4TimeSlots {...NO_ROWS_PROPS} />)

    expect(screen.queryByText(/20:00/)).toBeNull()
    expect(screen.queryByText(/09:00/)).toBeNull()
  })
})

describe('Step4TimeSlots（既存スロットあり）', () => {
  const ROW = {
    slot_id: 41,
    slot_name: '通勤時間',
    environment: 'MOBILE' as const,
    weekdays: [0, 1, 2, 3, 4],
    duration_minutes: 60,
    others_minutes: 0,
    minutes: 0,
    is_over_capacity: false,
  }

  function Harness({ onChangeMinutes }: { onChangeMinutes: (slotId: number, minutes: string) => void }) {
    const [values, setValues] = useState<SlotAllocationFormValues>({})
    return (
      <Step4TimeSlots
        {...NO_ROWS_PROPS}
        rows={[ROW]}
        values={values}
        onChangeMinutes={(slotId, minutes) => {
          onChangeMinutes(slotId, minutes)
          setValues((current) => ({ ...current, [slotId]: minutes }))
        }}
      />
    )
  }

  it('shows the allocation table instead of the simple hour inputs', async () => {
    const user = userEvent.setup()
    const onChangeMinutes = vi.fn()
    render(<Harness onChangeMinutes={onChangeMinutes} />)

    expect(screen.queryByLabelText(t('goals.examWizard.step4.weekdayHoursLabel'))).toBeNull()
    await user.type(screen.getByRole('spinbutton'), '30')

    expect(onChangeMinutes).toHaveBeenCalledWith(41, '3')
    expect(onChangeMinutes).toHaveBeenLastCalledWith(41, '30')
  })
})
