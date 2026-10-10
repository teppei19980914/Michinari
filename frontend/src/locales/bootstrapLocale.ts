import { isLocale, setLocale } from './t'

/** 起動時に取得した`display.locale`文字列を反映する（main.tsxのブートストラップから呼ぶ）。
 *
 * 未知の値（将来``_ALLOWED_LOCALES``に無い値が保存されていた場合等）は既定のjaのまま
 * 無視する。設定取得そのものに失敗した場合（main.tsx側のcatch）と同じ「何もしない」扱いに
 * 揃えることで、言語の反映に失敗しても起動自体は止めない。 */
export function applyBootstrapLocale(locale: string): void {
  if (!isLocale(locale)) {
    return
  }
  setLocale(locale)
  document.documentElement.lang = locale
}
