import { useEffect, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSettings } from '../api/settings'
import { QUERY_KEYS } from '../constants/queryKeys'
import { resolveTheme, writeDisplayPreference } from '../hooks/useDisplayPreferenceStorage'

/**
 * 表示設定（テーマ・アクセントカラー・フォントサイズ）を取得し、`<html>`のdata属性へ
 * 反映する（UIリッチ化）。`frontend/index.html`のインラインスクリプトが初回描画時に
 * localStorageキャッシュ由来の既定値を先に当てているため、ここでの反映はサーバ値が
 * 確定した後の「正しい値への上書き」として働く。
 *
 * `SettingsPage.tsx`と同じ`QUERY_KEYS.settings()`を使うため、react-queryのキャッシュ共有
 * により二重フェッチにはならない。
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const { data: settings } = useQuery({ queryKey: QUERY_KEYS.settings(), queryFn: getSettings })

  useEffect(() => {
    if (!settings) {
      return
    }
    const { theme, accent_color: accentColor, font_scale: fontScale } = settings.display
    const root = document.documentElement
    root.setAttribute('data-theme', resolveTheme(theme))
    root.setAttribute('data-accent', accentColor)
    root.setAttribute('data-font-scale', fontScale)
    writeDisplayPreference({ themePreference: theme, accentColor, fontScale })
  }, [settings])

  useEffect(() => {
    // theme="system"の間だけ、OSの明暗切替をリアルタイムに反映する。
    if (!settings || settings.display.theme !== 'system') {
      return
    }
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      document.documentElement.setAttribute('data-theme', media.matches ? 'dark' : 'light')
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [settings])

  return <>{children}</>
}
