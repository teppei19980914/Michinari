import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { HeaderVisibilityContext } from './headerVisibilityContext'

/** 小さな揺れ（トラックパッドの慣性スクロール等）でヘッダーがちらつかないための閾値(px)。 */
const SCROLL_DELTA_THRESHOLD_PX = 8
/** この高さ以下にいる間は、スクロール方向に関わらず常にヘッダーを表示する。 */
const ALWAYS_VISIBLE_BELOW_PX = 16

/**
 * スクロール連動のヘッダー開閉（UIリッチ化、`GlobalNav`・`GoalTabBar`共通）。
 *
 * scrollイベントの購読はこのProvider1箇所に集約し、`GlobalNav`・`GoalTabBar`の両方が
 * 同じ可視状態（Context）を参照する（二重購読によるタイミングのズレを防ぐ、
 * CODING_RULES.md①DRYの原則。このリポジトリにスクロール監視フックの前例が無いため新規に
 * 用意した）。可視状態はCSS変数`--subheader-offset`としても`<html>`へ反映し、
 * `GoalTabBar`の`sticky`位置（`GlobalNav`の下／`GlobalNav`が隠れた分だけ詰める）に使う。
 *
 * `GlobalNav`はルータの`Layout`直下に常駐しアンマウントされないため、前の画面で閉じたまま
 * 次の画面へ遷移すると気づけない。ルート遷移時に表示状態をリセットするが、Providerの
 * 子（アプリ全体）を再マウントしたくないため、React公式の「レンダー中に状態を調整する」
 * パターン（https://react.dev/learn/you-might-not-need-an-effect）を使い、
 * `useEffect`内での同期的なsetStateを避けている。
 */
export function HeaderVisibilityProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const [visible, setVisible] = useState(true)
  const [renderedPathname, setRenderedPathname] = useState(pathname)
  const lastScrollYRef = useRef(0)

  if (pathname !== renderedPathname) {
    setRenderedPathname(pathname)
    setVisible(true)
  }

  useEffect(() => {
    // refの変更は描画中ではなくeffect内で行う（React refsは描画結果に不要な値であり、
    // 描画中に変更すると再描画されない場合がある）。
    lastScrollYRef.current = window.scrollY
  }, [renderedPathname])

  useEffect(() => {
    let ticking = false
    function handleScroll() {
      if (ticking) {
        return
      }
      ticking = true
      window.requestAnimationFrame(() => {
        const currentY = window.scrollY
        if (currentY <= ALWAYS_VISIBLE_BELOW_PX) {
          setVisible(true)
        } else {
          const delta = currentY - lastScrollYRef.current
          if (Math.abs(delta) > SCROLL_DELTA_THRESHOLD_PX) {
            setVisible(delta < 0)
          }
        }
        lastScrollYRef.current = currentY
        ticking = false
      })
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    document.documentElement.style.setProperty(
      '--subheader-offset',
      visible ? 'var(--global-nav-height)' : '0px',
    )
  }, [visible])

  return (
    <HeaderVisibilityContext.Provider value={visible}>{children}</HeaderVisibilityContext.Provider>
  )
}
