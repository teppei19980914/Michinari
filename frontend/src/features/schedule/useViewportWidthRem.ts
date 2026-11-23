import { useEffect, useState } from 'react'

//: resizeイベントの間引き間隔（ms）。ウィンドウのドラッグリサイズ中は高頻度で発火するため、
//: 1日分の幅の再計算（パフォーマンスレビュー指摘）を間引く。
const RESIZE_DEBOUNCE_MS = 100

/**
 * 1日分の幅（D-20）の算出に使う、表示領域の目安の幅（rem）。`window.innerWidth`を
 * ルートのフォントサイズ（`--font-scale`、D-20「文字サイズの設定に追従」）で割る。
 * `ResizeObserver`によるコンテナ実測は行わない（`components/textTruncation.ts`と同じ方針、
 * CODING_RULES.md「保守性（複雑度）」。jsdomでの追加のモック設定も不要になる）。
 */
export function useViewportWidthRem(): number {
  const [widthRem, setWidthRem] = useState(0)

  useEffect(() => {
    function update() {
      const rootFontSizePx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      setWidthRem(window.innerWidth / rootFontSizePx)
    }
    update()

    let timeoutId: ReturnType<typeof setTimeout> | undefined
    function debouncedUpdate() {
      clearTimeout(timeoutId)
      timeoutId = setTimeout(update, RESIZE_DEBOUNCE_MS)
    }

    window.addEventListener('resize', debouncedUpdate)
    return () => {
      clearTimeout(timeoutId)
      window.removeEventListener('resize', debouncedUpdate)
    }
  }, [])

  return widthRem
}
