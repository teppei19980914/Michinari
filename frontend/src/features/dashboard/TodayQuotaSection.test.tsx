/** 本日のノルマ表示を固定する（Phase 35）。
 *
 * 予備日（バッファ日）はノルマを積まない日であり、目標分量を0・目標時間を「—」で示す必要がある。
 * ここが崩れると予備日にノルマが出て、休むべき日に無理をさせる（あるいは逆に平常日のノルマが
 * 消える）。目標ごとの見出しは、複数目標のノルマをまとめて渡されたときだけ出す。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, MATERIAL_ID, makeTodayQuotaEntry } from '../../test/fixtures'
import { TodayQuotaSection } from './TodayQuotaSection'

const SLOT_NAMES = ['朝の枠']

afterEach(() => {
  cleanup()
})

describe('TodayQuotaSection', () => {
  it('tells the user there is nothing to do today', () => {
    renderWithProviders(
      <TodayQuotaSection todayQuota={[]} availableSlotNames={SLOT_NAMES} isBufferDay={false} />,
    )

    expect(screen.getByText(t('dashboard.todayQuota.empty'))).toBeDefined()
  })

  it('shows the quota and the target minutes on a normal day', () => {
    renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry({ daily_quota: 12.34, target_minutes: 30.6 })]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay={false}
      />,
    )

    // 小数第1位で丸めて示す（細かすぎる数字は行動の判断に使えないため）。
    expect(screen.getByText(/12\.3/)).toBeDefined()
    expect(screen.getByText(`31${t('common.unit.minutes')}`)).toBeDefined()
  })

  it('zeroes the quota and withholds the target minutes on a buffer day', () => {
    renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry({ daily_quota: 12, target_minutes: 30 })]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay
      />,
    )

    expect(screen.getByText(t('dashboard.todayQuota.bufferDayNotice'))).toBeDefined()
    expect(screen.getByText(`0${'問'}`)).toBeDefined()
    expect(screen.getByText(t('dashboard.todayQuota.targetMinutesUnavailable'))).toBeDefined()
  })

  it('withholds the target minutes when the server could not compute one', () => {
    renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry({ target_minutes: null })]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay={false}
      />,
    )

    expect(screen.getByText(t('dashboard.todayQuota.targetMinutesUnavailable'))).toBeDefined()
  })

  it('lists the usable slots only when there is any', () => {
    const { unmount } = renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry()]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay={false}
      />,
    )
    expect(screen.getByText(new RegExp(t('dashboard.todayQuota.availableSlots')))).toBeDefined()

    unmount()
    renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry()]}
        availableSlotNames={[]}
        isBufferDay={false}
      />,
    )

    expect(screen.queryByText(new RegExp(t('dashboard.todayQuota.availableSlots')))).toBeNull()
  })

  it('heads each group with the goal name only when several goals are listed', () => {
    const { unmount } = renderWithProviders(
      <TodayQuotaSection
        todayQuota={[makeTodayQuotaEntry()]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay={false}
      />,
    )
    // 1目標だけなら見出しは冗長なので出さない。
    expect(screen.queryByRole('heading', { name: '目標A' })).toBeNull()

    unmount()
    renderWithProviders(
      <TodayQuotaSection
        todayQuota={[
          makeTodayQuotaEntry(),
          makeTodayQuotaEntry({
            goal_id: GOAL_ID + 1,
            goal_name: '目標B',
            material_id: MATERIAL_ID + 1,
            material_name: '教材B',
          }),
        ]}
        availableSlotNames={SLOT_NAMES}
        isBufferDay={false}
      />,
    )

    expect(screen.getByRole('heading', { name: '目標A' })).toBeDefined()
    expect(screen.getByRole('heading', { name: '目標B' })).toBeDefined()
  })
})
