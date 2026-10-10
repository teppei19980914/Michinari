/** スクロール連動ヘッダー開閉（UIリッチ化）。下スクロールで非表示・上スクロールで即時表示、
 * 最上部付近では常に表示、ルート遷移でリセットされることを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { useHeaderVisibility } from './headerVisibilityContext'
import { HeaderVisibilityProvider } from './HeaderVisibilityProvider'

function setScrollY(value: number) {
  Object.defineProperty(window, 'scrollY', { value, configurable: true })
}

function fireScroll() {
  act(() => {
    window.dispatchEvent(new Event('scroll'))
  })
}

function Probe() {
  const visible = useHeaderVisibility()
  return <span data-testid="visible">{String(visible)}</span>
}

function NavigateButton({ to }: { to: string }) {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => navigate(to)}>
      go
    </button>
  )
}

function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <HeaderVisibilityProvider>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <Probe />
                <NavigateButton to="/other" />
              </>
            }
          />
        </Routes>
      </HeaderVisibilityProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setScrollY(0)
  // requestAnimationFrameを同期実行に寄せ、スクロールイベントの検証をテスト内で即座に行えるようにする。
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    callback(0)
    return 0
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('HeaderVisibilityProvider', () => {
  it('starts visible', () => {
    renderAtPath('/')
    expect(screen.getByTestId('visible').textContent).toBe('true')
  })

  it('hides after scrolling down past the threshold', () => {
    renderAtPath('/')

    setScrollY(200)
    fireScroll()

    expect(screen.getByTestId('visible').textContent).toBe('false')
  })

  it('shows again immediately after scrolling up past the threshold', () => {
    renderAtPath('/')
    setScrollY(200)
    fireScroll()
    expect(screen.getByTestId('visible').textContent).toBe('false')

    setScrollY(150)
    fireScroll()

    expect(screen.getByTestId('visible').textContent).toBe('true')
  })

  it('ignores a scroll delta smaller than the threshold', () => {
    renderAtPath('/')
    setScrollY(200)
    fireScroll()
    expect(screen.getByTestId('visible').textContent).toBe('false')

    setScrollY(203)
    fireScroll()

    // 8px以下の揺れでは非表示のまま変化しない。
    expect(screen.getByTestId('visible').textContent).toBe('false')
  })

  it('stays visible while near the top regardless of direction', () => {
    renderAtPath('/')
    setScrollY(10)
    fireScroll()

    expect(screen.getByTestId('visible').textContent).toBe('true')
  })

  it('resets to visible on route change', () => {
    renderAtPath('/')
    setScrollY(200)
    fireScroll()
    expect(screen.getByTestId('visible').textContent).toBe('false')

    act(() => {
      screen.getByRole('button', { name: 'go' }).click()
    })

    expect(screen.getByTestId('visible').textContent).toBe('true')
  })

  it('throttles rapid scroll events into a single animation frame', () => {
    let pendingCallback: FrameRequestCallback | null = null
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      pendingCallback = callback
      return 0
    })
    renderAtPath('/')

    setScrollY(200)
    act(() => {
      window.dispatchEvent(new Event('scroll'))
      // 直前のrAFがまだ解決していない間に発生した2回目のscrollは、スロットルにより
      // 素通りする（tickingフラグの早期returnを通る）。
      window.dispatchEvent(new Event('scroll'))
    })
    expect(screen.getByTestId('visible').textContent).toBe('true')

    act(() => {
      pendingCallback?.(0)
    })

    expect(screen.getByTestId('visible').textContent).toBe('false')
  })

  it('writes the visibility to the --subheader-offset CSS variable', () => {
    renderAtPath('/')
    expect(document.documentElement.style.getPropertyValue('--subheader-offset')).toBe(
      'var(--global-nav-height)',
    )

    setScrollY(200)
    fireScroll()

    expect(document.documentElement.style.getPropertyValue('--subheader-offset')).toBe('0px')
  })
})

describe('useHeaderVisibility', () => {
  it('defaults to true outside of a provider', () => {
    render(<Probe />)
    expect(screen.getByTestId('visible').textContent).toBe('true')
  })
})
