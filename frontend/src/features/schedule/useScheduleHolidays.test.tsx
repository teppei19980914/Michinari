/** useScheduleHolidays の回帰テスト。カバレッジ閾値の対象外（vite.config.ts
 * `src/**\/use*.ts` 除外）だが、表示期間の算出・祝日クエリの有効化という非自明な
 * 分岐を持つため、OPERATIONS.md「フロントエンドのテストとカバレッジ」の方針に沿って
 * 直接テストする。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useScheduleHolidays } from './useScheduleHolidays'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

const getHolidayCoverage = vi.hoisted(() => vi.fn())
vi.mock('../../api/resources', () => ({ getHolidayCoverage }))

function item(overrides: Partial<ScheduleDraftItem> = {}): ScheduleDraftItem {
  return {
    key: 'id:1',
    id: 1,
    tempKey: null,
    title: '作業A',
    description: null,
    plannedStartDate: '2026-11-01',
    plannedEndDate: '2026-11-10',
    status: 'NOT_STARTED',
    actualStartDate: null,
    actualEndDate: null,
    cells: {},
    ...overrides,
  }
}

function setup(items: ScheduleDraftItem[], today: string | null, enabled: boolean) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useScheduleHolidays(items, today, enabled), { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useScheduleHolidays', () => {
  it('enabled=falseの間は祝日を取得しない', async () => {
    getHolidayCoverage.mockResolvedValue({ holidays: [], year_from: 1955, year_to: 2027 })
    setup([item()], '2026-11-23', false)
    await waitFor(() => expect(getHolidayCoverage).not.toHaveBeenCalled())
  })

  it('表示期間（全行の予定日と本日のうち最早〜最遅）で祝日を取得する', async () => {
    getHolidayCoverage.mockResolvedValue({
      holidays: [{ holiday_date: '2026-11-03', name: '文化の日' }],
      year_from: 1955,
      year_to: 2027,
    })
    const { result } = setup([item()], '2026-11-23', true)

    await waitFor(() => expect(getHolidayCoverage).toHaveBeenCalledWith('2026-11-01', '2026-11-23'))
    await waitFor(() => expect(result.current.holidayIsoDates.has('2026-11-03')).toBe(true))
    expect(result.current.holidayYearFrom).toBe(1955)
    expect(result.current.holidayYearTo).toBe(2027)
  })

  it('取得結果が無い間はholidayIsoDatesが空集合、年範囲はnull', () => {
    getHolidayCoverage.mockReturnValue(new Promise(() => {}))
    const { result } = setup([item()], '2026-11-23', true)
    expect(result.current.holidayIsoDates.size).toBe(0)
    expect(result.current.holidayYearFrom).toBeNull()
    expect(result.current.holidayYearTo).toBeNull()
  })
})
