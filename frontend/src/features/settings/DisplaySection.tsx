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

/** 表示設定の各セレクト欄（言語・テーマ・分析粒度・アクセントカラー・フォントサイズ）は
 * 同じ形（ラベル＋select＋選択肢の翻訳）を繰り返すため、1つに集約する（CODING_RULES.md
 * ①DRYの原則）。 */
function DisplaySelect({
  label,
  value,
  onChange,
  options,
  translateOption,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: readonly string[]
  translateOption: (value: string) => string
}) {
  return (
    <label className="flex flex-1 flex-col gap-1 text-sm text-text-secondary">
      {label}
      <select
        className="rounded-md border border-border-strong px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {translateOption(option)}
          </option>
        ))}
      </select>
    </label>
  )
}

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
      <h2 className="font-medium text-text-primary">{t('settings.display.title')}</h2>
      <div className="flex gap-3">
        <DisplaySelect
          label={t('settings.display.localeLabel')}
          value={locale}
          onChange={setLocale}
          options={LOCALES}
          translateOption={(value) => t(`settings.display.locale.${value}`)}
        />
        <DisplaySelect
          label={t('settings.display.themeLabel')}
          value={theme}
          onChange={setTheme}
          options={THEMES}
          translateOption={(value) => t(`settings.display.theme.${value}`)}
        />
        <DisplaySelect
          label={t('settings.display.defaultGranularityLabel')}
          value={granularity}
          onChange={setGranularity}
          options={GRANULARITIES}
          translateOption={(value) => t(`settings.display.granularity.${value}`)}
        />
      </div>
      <div className="flex gap-3">
        <DisplaySelect
          label={t('settings.display.accentColorLabel')}
          value={accentColor}
          onChange={setAccentColor}
          options={ACCENT_COLORS}
          translateOption={(value) => t(`settings.display.accentColor.${value}`)}
        />
        <DisplaySelect
          label={t('settings.display.fontScaleLabel')}
          value={fontScale}
          onChange={setFontScale}
          options={FONT_SCALES}
          translateOption={(value) => t(`settings.display.fontScale.${value}`)}
        />
      </div>
      <div className="flex justify-end">
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
