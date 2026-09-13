import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { buildDesktopSettingsPayload, resolveDesktopSettingsGuard } from './desktopSettings'

/**
 * デスクトップ常駐・記録リマインドの設定（SC-11、実装スコープA〜C）。
 *
 * 「Windows 起動時に自動で起動する」はレジストリへの登録を伴うが、その反映はアプリの
 * 起動時にバックエンドが行う（`app/desktop/autostart.py`）。ここでは設定値の保存だけを行う。
 */
export function DesktopSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [openBrowser, setOpenBrowser] = useState(settings.desktop.open_browser_on_startup)
  const [launchAtLogin, setLaunchAtLogin] = useState(settings.desktop.launch_at_login)
  const [notificationEnabled, setNotificationEnabled] = useState(
    settings.desktop.notification_enabled,
  )
  const [notificationTime, setNotificationTime] = useState(settings.desktop.notification_time)

  const guard = resolveDesktopSettingsGuard(notificationEnabled, notificationTime)

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({
        desktop: buildDesktopSettingsPayload({
          openBrowserOnStartup: openBrowser,
          launchAtLogin: launchAtLogin,
          notificationEnabled: notificationEnabled,
          notificationTime: notificationTime,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.desktop.title')}</h2>
      <p className="text-sm text-gray-500">{t('settings.desktop.description')}</p>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={openBrowser}
          onChange={(e) => setOpenBrowser(e.target.checked)}
        />
        {t('settings.desktop.openBrowserLabel')}
      </label>
      <p className="text-xs text-gray-500">{t('settings.desktop.openBrowserHelp')}</p>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={launchAtLogin}
          onChange={(e) => setLaunchAtLogin(e.target.checked)}
        />
        {t('settings.desktop.launchAtLoginLabel')}
      </label>
      <p className="text-xs text-gray-500">{t('settings.desktop.launchAtLoginHelp')}</p>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={notificationEnabled}
          onChange={(e) => setNotificationEnabled(e.target.checked)}
        />
        {t('settings.desktop.notificationEnabledLabel')}
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('settings.desktop.notificationTimeLabel')}
        <Input
          type="time"
          value={notificationTime}
          disabled={!notificationEnabled}
          onChange={(e) => setNotificationTime(e.target.value)}
        />
      </label>
      <p className="text-xs text-gray-500">{t('settings.desktop.notificationHelp')}</p>
      {guard.errorKey !== null && <p className="text-sm text-red-600">{t(guard.errorKey)}</p>}

      <div className="flex justify-end">
        <Button disabled={mutation.isPending || !guard.canSubmit} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
