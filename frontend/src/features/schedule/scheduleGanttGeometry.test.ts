import { getDay, parseISO } from 'date-fns'
import { describe, expect, it } from 'vitest'
import {
  computeActualBandRange,
  computeBandRem,
  computeDayTypeRuns,
  computeDayWidthRem,
  computeDisplayRange,
  computeInitialScrollLeftRem,
  computeTodayLineLeftRem,
  countDaysInclusive,
  type ScheduleGanttItemInput,
} from './scheduleGanttGeometry'

function item(overrides: Partial<ScheduleGanttItemInput>): ScheduleGanttItemInput {
  return {
    status: 'NOT_STARTED',
    planned_start_date: '2026-11-10',
    planned_end_date: '2026-11-15',
    actual_start_date: null,
    actual_end_date: null,
    ...overrides,
  }
}

describe('computeDisplayRange', () => {
  it('行が無い場合は本日のみの1日を返す', () => {
    expect(computeDisplayRange([], '2026-11-23')).toEqual({
      startIso: '2026-11-23',
      endIso: '2026-11-23',
    })
  })

  it('全行の予定日と本日のうち最早〜最遅を返す', () => {
    const range = computeDisplayRange([item({})], '2026-11-23')
    expect(range).toEqual({ startIso: '2026-11-10', endIso: '2026-11-23' })
  })

  it('実績日が予定日より外側にある場合はそれを含める', () => {
    const range = computeDisplayRange(
      [
        item({
          status: 'DONE',
          planned_start_date: '2026-11-01',
          planned_end_date: '2026-11-05',
          actual_start_date: '2026-11-02',
          actual_end_date: '2026-11-30',
        }),
      ],
      '2026-11-23',
    )
    expect(range).toEqual({ startIso: '2026-11-01', endIso: '2026-11-30' })
  })
})

describe('countDaysInclusive', () => {
  it('両端を含めた日数を返す（同日なら1）', () => {
    expect(countDaysInclusive({ startIso: '2026-11-05', endIso: '2026-11-05' })).toBe(1)
    expect(countDaysInclusive({ startIso: '2026-11-01', endIso: '2026-11-05' })).toBe(5)
  })
})

describe('computeDayWidthRem', () => {
  it('コンテナ幅÷日数が範囲内ならそのまま使う', () => {
    expect(computeDayWidthRem(40, 100, 1.75, 4.5)).toBe(2.5)
  })

  it('下限を下回る場合は下限にクランプする', () => {
    expect(computeDayWidthRem(100, 100, 1.75, 4.5)).toBe(1.75)
  })

  it('上限を上回る場合は上限にクランプする', () => {
    expect(computeDayWidthRem(10, 100, 1.75, 4.5)).toBe(4.5)
  })

  it('日数が0以下なら上限を返す（空のときの案内が表示されるため実際には使われない）', () => {
    expect(computeDayWidthRem(0, 100, 1.75, 4.5)).toBe(4.5)
  })
})

describe('computeBandRem', () => {
  it('表示期間の開始日からの位置と、両端を含めた幅を算出する', () => {
    const band = computeBandRem('2026-11-01', '2026-11-03', '2026-11-05', 2)
    expect(band).toEqual({ leftRem: 4, widthRem: 6 })
  })

  it('開始日が表示期間の先頭と同じならleftRemは0', () => {
    const band = computeBandRem('2026-11-01', '2026-11-01', '2026-11-01', 2)
    expect(band).toEqual({ leftRem: 0, widthRem: 2 })
  })
})

describe('computeActualBandRange', () => {
  it('完了していて実績日が両方あれば実績期間を返す', () => {
    const range = computeActualBandRange(
      item({ status: 'DONE', actual_start_date: '2026-11-11', actual_end_date: '2026-11-14' }),
      '2026-11-23',
    )
    expect(range).toEqual({ startIso: '2026-11-11', endIso: '2026-11-14' })
  })

  it('完了していても実績終了日が無ければnull（データ上は発生しない想定の防御的分岐）', () => {
    const range = computeActualBandRange(
      item({ status: 'DONE', actual_start_date: '2026-11-11', actual_end_date: null }),
      '2026-11-23',
    )
    expect(range).toBeNull()
  })

  it('進行中で実績終了日が無い場合は本日まで伸ばす（D-17）', () => {
    const range = computeActualBandRange(
      item({ status: 'IN_PROGRESS', actual_start_date: '2026-11-11', actual_end_date: null }),
      '2026-11-23',
    )
    expect(range).toEqual({ startIso: '2026-11-11', endIso: '2026-11-23' })
  })

  it('中止で実績開始日のみある場合は単日の実績帯を返す', () => {
    const range = computeActualBandRange(
      item({ status: 'CANCELLED', actual_start_date: '2026-11-11', actual_end_date: null }),
      '2026-11-23',
    )
    expect(range).toEqual({ startIso: '2026-11-11', endIso: '2026-11-11' })
  })

  it('未着手は常に実績帯を持たない', () => {
    expect(computeActualBandRange(item({ status: 'NOT_STARTED' }), '2026-11-23')).toBeNull()
  })

  it('中止で実績日が無ければ実績帯を持たない', () => {
    expect(computeActualBandRange(item({ status: 'CANCELLED' }), '2026-11-23')).toBeNull()
  })
})

describe('computeTodayLineLeftRem', () => {
  it('表示期間の開始日からの位置に、セル幅の半分を加えた位置を返す', () => {
    expect(computeTodayLineLeftRem('2026-11-01', '2026-11-04', 2)).toBe(7)
  })
})

describe('computeDayTypeRuns', () => {
  it('土曜・日曜（祝日無し）の連続区間を1つの矩形にまとめる', () => {
    const rangeStart = '2026-11-01'
    const rangeEnd = '2026-11-30'
    const dayWidthRem = 2
    const runs = computeDayTypeRuns(rangeStart, rangeEnd, new Set(), dayWidthRem)

    // 日ごとに期待されるtype（date-fnsのgetDayで独立に算出し、実装と同じ計算を2重化しない）
    const expectedTypesByOffset: ('saturday' | 'holiday' | null)[] = []
    for (let offset = 0; offset <= 29; offset += 1) {
      const date = new Date(2026, 10, 1 + offset)
      const dow = getDay(date)
      expectedTypesByOffset.push(dow === 0 ? 'holiday' : dow === 6 ? 'saturday' : null)
    }

    // runsが示す区間をoffsetの配列に展開し、元のtype判定と一致することを確認する。
    const reconstructed: (string | null)[] = Array(30).fill(null)
    for (const run of runs) {
      const startOffset = Math.round(run.leftRem / dayWidthRem)
      const lengthDays = Math.round(run.widthRem / dayWidthRem)
      for (let i = 0; i < lengthDays; i += 1) {
        reconstructed[startOffset + i] = run.type
      }
    }
    expect(reconstructed).toEqual(expectedTypesByOffset)
  })

  it('祝日の日付が渡された場合はholidayとして扱う（平日に祝日が1日だけある場合）', () => {
    // 2026-11-03は火曜日（文化の日）を祝日として渡すケースを想定し、date-fnsで曜日を確認する。
    const weekday = getDay(parseISO('2026-11-03'))
    expect(weekday).not.toBe(0)
    expect(weekday).not.toBe(6)

    const runs = computeDayTypeRuns(
      '2026-11-02',
      '2026-11-04',
      new Set(['2026-11-03']),
      2,
    )
    expect(runs).toContainEqual({ type: 'holiday', leftRem: 2, widthRem: 2 })
  })

  it('表示期間が逆転している場合は空配列を返す', () => {
    expect(computeDayTypeRuns('2026-11-10', '2026-11-05', new Set(), 2)).toEqual([])
  })
})

describe('computeInitialScrollLeftRem', () => {
  it('本日の位置がスクロール可能範囲内ならそのまま使う', () => {
    expect(computeInitialScrollLeftRem(50, 200, 100)).toBe(50)
  })

  it('本日の位置が右端を超える場合は最大スクロール位置に止める', () => {
    expect(computeInitialScrollLeftRem(180, 200, 100)).toBe(100)
  })

  it('本日の位置が負になることはないが0未満は0にクランプする', () => {
    expect(computeInitialScrollLeftRem(-5, 200, 100)).toBe(0)
  })
})
