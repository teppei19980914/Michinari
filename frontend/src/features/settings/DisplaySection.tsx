import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'

const THEMES = ['system', 'light', 'dark'] as const
const GRANULARITIES = ['DAY', 'WEEK', 'MONTH'] as const
const LOCALES = ['ja'] as const
const ACCENT_COLORS = ['blue', 'green', 'purple', 'orange'] as const
const FONT_SCALES = ['small', 'standard', 'large'] as const

/** 表示設定（仕様書6.11「表示言語、テーマ、既定の表示粒度」）。 */
export function DisplaySection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [locale, setLocale] = useState(settings.display.locale)
  const [theme, setTheme] = useState(settings.display.theme)
  const [granularity, setGranularity] = useState(settings.display.default_granularity)
  const [accentColor, setAccentColor] = useState(settings.display.accent_color)
  const [fontScale, setFontScale] = useState(settings.display.font_scale)

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({
        display: {
          locale,
          theme,
          default_granularity: granularity,
          accent_color: accentColor,
          font_scale: fontScale,
        },
      }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.display.title')}</h2>
      <div className="flex gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.display.localeLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={locale}
            onChange={(e) => setLocale(e.target.value)}
          >
            {LOCALES.map((value) => (
              <option key={value} value={value}>
                {t(`settings.display.locale.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.display.themeLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
          >
            {THEMES.map((value) => (
              <option key={value} value={value}>
                {t(`settings.display.theme.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.display.defaultGranularityLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
          >
            {GRANULARITIES.map((value) => (
              <option key={value} value={value}>
                {t(`settings.display.granularity.${value}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.display.accentColorLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={accentColor}
            onChange={(e) => setAccentColor(e.target.value)}
          >
            {ACCENT_COLORS.map((value) => (
              <option key={value} value={value}>
                {t(`settings.display.accentColor.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.display.fontScaleLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={fontScale}
            onChange={(e) => setFontScale(e.target.value)}
          >
            {FONT_SCALES.map((value) => (
              <option key={value} value={value}>
                {t(`settings.display.fontScale.${value}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex justify-end">
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
