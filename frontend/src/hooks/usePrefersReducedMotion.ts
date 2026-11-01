import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function readPrefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(QUERY).matches
}

/**
 * OS設定の「視差効果を減らす」（`prefers-reduced-motion: reduce`）を購読する
 * （開発Todo_道のりマップ_v1.0.md §0 要件5「演出やアニメーションはprefers-reduced-motionの
 * 設定に従う」）。初回表示時の「現在地まで歩く」アニメーションの分岐に使う。
 */
export function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(readPrefersReducedMotion)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }
    const mediaQueryList = window.matchMedia(QUERY)
    const handleChange = () => setPrefersReducedMotion(mediaQueryList.matches)
    mediaQueryList.addEventListener('change', handleChange)
    return () => mediaQueryList.removeEventListener('change', handleChange)
  }, [])

  return prefersReducedMotion
}
