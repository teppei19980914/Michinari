/**
 * 表示設定（テーマ・アクセントカラー・フォントサイズ）のlocalStorageキャッシュ（UIリッチ化）。
 *
 * サーバの`/settings`応答が正であり、ここは初回描画時に既定値が一瞬見える問題（FOUC）を
 * 避けるためだけの表示用キャッシュ。保存されるキー名・JSON形状は、Reactが読み込まれる前に
 * 実行される`frontend/index.html`のインラインスクリプトと完全に一致させる必要がある
 * （インラインスクリプトはプレーンJSのためこのファイルをimportできず、意図的に重複させている。
 * 変更時は両方を確認すること）。このリポジトリでlocalStorageを使うのはここが初めて。
 */

export const DISPLAY_PREFERENCE_STORAGE_KEY = 'michinari.displayPreference'

export type DisplayPreference = {
  /** 設定画面で選べる値（system/light/dark）。実際の明暗はresolveTheme()で解決する。 */
  themePreference: string
  accentColor: string
  fontScale: string
}

function isDisplayPreference(value: unknown): value is DisplayPreference {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.themePreference === 'string' &&
    typeof candidate.accentColor === 'string' &&
    typeof candidate.fontScale === 'string'
  )
}

/** 保存済みの表示設定キャッシュを読む。壊れている・未保存の場合はnull（既定値は呼び出し側が持つ）。 */
export function readDisplayPreference(): DisplayPreference | null {
  try {
    const raw = window.localStorage.getItem(DISPLAY_PREFERENCE_STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed: unknown = JSON.parse(raw)
    return isDisplayPreference(parsed) ? parsed : null
  } catch {
    // プライベートブラウジング等でlocalStorageが使えない環境でも、サーバ値による
    // 表示自体は動作するため失敗は無視してよい。
    return null
  }
}

export function writeDisplayPreference(preference: DisplayPreference): void {
  try {
    window.localStorage.setItem(DISPLAY_PREFERENCE_STORAGE_KEY, JSON.stringify(preference))
  } catch {
    // 同上の理由で失敗は無視してよい。
  }
}

/** themePreference（system/light/dark）から実際の明暗を解決する。
 * インラインスクリプト（frontend/index.html）にも同じロジックを意図的に重複させている。 */
export function resolveTheme(themePreference: string): 'light' | 'dark' {
  if (themePreference === 'light' || themePreference === 'dark') {
    return themePreference
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
