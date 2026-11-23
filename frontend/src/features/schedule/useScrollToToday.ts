import { useEffect, type RefObject } from 'react'
import { computeInitialScrollLeftRem } from './scheduleGanttGeometry'

/**
 * 初期表示時と「今日へ」ボタン（`goToTodaySignal`の変化）で、本日が固定列のすぐ右に
 * 来る位置へスクロールする（D-23・D-26）。
 */
export function useScrollToToday(
  scrollRef: RefObject<HTMLDivElement | null>,
  goToTodaySignal: number,
  viewportWidthRem: number,
  fixedAreaWidthRem: number,
  ganttWidthRem: number,
  todayLineLeftRem: number,
) {
  useEffect(() => {
    const element = scrollRef.current
    if (!element || viewportWidthRem === 0) return
    const rootFontSizePx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
    const totalWidthRem = fixedAreaWidthRem + ganttWidthRem
    const scrollLeftRem = computeInitialScrollLeftRem(todayLineLeftRem, totalWidthRem, viewportWidthRem)
    element.scrollLeft = scrollLeftRem * rootFontSizePx
  }, [scrollRef, goToTodaySignal, viewportWidthRem, fixedAreaWidthRem, ganttWidthRem, todayLineLeftRem])
}
