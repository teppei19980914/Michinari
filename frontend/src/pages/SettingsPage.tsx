import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { ApiError } from '../api/client'
import { getSettings } from '../api/settings'
import { AiConnectionSection } from '../features/settings/AiConnectionSection'
import { ThresholdSection } from '../features/settings/ThresholdSection'
import { PromptDegradationSection } from '../features/settings/PromptDegradationSection'
import { DisplaySection } from '../features/settings/DisplaySection'
import { LogSection } from '../features/settings/LogSection'
import { PromptTemplateSection } from '../features/settings/PromptTemplateSection'

/** SC-11 設定（仕様書6.11「全ての設定項目は画面上から変更可能とする」）。 */
export function SettingsPage() {
  const settingsQuery = useQuery({ queryKey: ['settings'], queryFn: getSettings })

  if (settingsQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (settingsQuery.isError || !settingsQuery.data) {
    const error = settingsQuery.error
    const message = error instanceof ApiError ? error.localizedMessage : t('errors.default')
    return <p className="p-6 text-sm text-red-600">{message}</p>
  }

  const settings = settingsQuery.data

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{t('settings.title')}</h1>
        <Link to={ROUTES.settingsData} className="text-sm text-blue-600 hover:underline">
          {t('settings.dataManagementLink')}
        </Link>
      </div>
      <AiConnectionSection settings={settings} />
      <ThresholdSection settings={settings} />
      <PromptDegradationSection settings={settings} />
      <DisplaySection settings={settings} />
      <PromptTemplateSection />
      <LogSection settings={settings} />
    </div>
  )
}
