/** AI接続の認証状況と再認証（仕様書6.11）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた AiConnectionSection
 * から切り出したものである。接続用パラメータはHost・PATのみに絞る（UIの簡素化）。
 * client_id・tenant_id・api_base_urlはEntraIDフォールバック認証専用で通常は空でよいため
 * 画面上には出さない（設計書 ロジック・プロンプト編16.2、データ構造編228〜229行）。
 *
 * 個人アクセストークンはこの部品が保持する。設定フォーム（保存対象）とは別物で、
 * 保存ではなく再認証にだけ使い、成功したら捨てる値だからである。 */
import { useState } from 'react'
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import type { AiStatusRead } from '../../api/ai'

export function AiAuthStatusCard({
  status,
  host,
  onChangeHost,
  isReauthenticating,
  onReauthenticate,
}: {
  status: AiStatusRead | undefined
  host: string
  onChangeHost: (value: string) => void
  isReauthenticating: boolean
  /** 入力された個人アクセストークンを渡す。成功時は呼び出し元が `clearToken` を呼ぶ。 */
  onReauthenticate: (personalAccessToken: string, clearToken: () => void) => void
}) {
  const [pat, setPat] = useState('')

  return (
    <div className="rounded-md border border-gray-200 p-3">
      <h3 className="text-sm font-medium text-gray-900">
        {t('settings.aiConnection.authStatus.title')}
      </h3>
      <p className="mt-1 text-sm text-gray-600">
        {status?.authenticated
          ? t('settings.aiConnection.authStatus.authenticated')
          : t('settings.aiConnection.authStatus.notAuthenticated')}
      </p>
      {status?.login_in_progress && (
        <p className="text-xs text-gray-500">
          {t('settings.aiConnection.authStatus.loginInProgress')}
        </p>
      )}
      {status && Object.keys(status.model_status).length > 0 && (
        <div className="mt-2 text-xs text-gray-500">
          <p>{t('settings.aiConnection.modelStatusTitle')}</p>
          <ul>
            {Object.entries(status.model_status).map(([model, ok]) => (
              <li key={model}>
                {model}: {ok ? '✓' : '×'}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('settings.aiConnection.hostLabel')}
          <Input value={host} onChange={(e) => onChangeHost(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('settings.aiConnection.authStatus.patLabel')}
          <Input type="password" value={pat} onChange={(e) => setPat(e.target.value)} />
        </label>
        <Button
          disabled={isReauthenticating || !pat}
          onClick={() => onReauthenticate(pat, () => setPat(''))}
        >
          {t('settings.aiConnection.authStatus.reauth')}
        </Button>
      </div>
    </div>
  )
}
