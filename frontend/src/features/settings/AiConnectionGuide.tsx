import { t } from '../../locales/t'

/**
 * AI接続手順の段階的な案内（仕様書6.11、非エンジニア向けエラー表示改善2026-09-19）。
 *
 * 「NewtonX Web版を開く」のリンク先は、接続先URL（Host、例: xxx.newton-x.net）を
 * そのまま使う。固定のURLを持たない（所属ごとにサブドメインが異なるため、HelpPage
 * 6.13節のFAQ参照）。Hostが未入力のうちはリンクではなく案内文のみを表示する。
 */
export function AiConnectionGuide({ host }: { host: string }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-blue-100 bg-blue-50 p-3 text-sm text-gray-700">
      <div>
        <p className="font-medium text-gray-900">{t('settings.aiConnection.guide.step1Title')}</p>
        {host ? (
          <a
            className="text-blue-700 underline"
            href={`https://${host}`}
            target="_blank"
            rel="noreferrer"
          >
            {t('settings.aiConnection.guide.step1LinkLabel')}
          </a>
        ) : (
          <p className="text-xs text-gray-500">
            {t('settings.aiConnection.guide.step1HostMissing')}
          </p>
        )}
      </div>

      <div>
        <p className="font-medium text-gray-900">{t('settings.aiConnection.guide.step2Title')}</p>
        <p>{t('settings.aiConnection.guide.step2Description')}</p>
        {/* ダミー画像。実際のスクリーンショットは後で frontend/public/help/ 配下の
            同名ファイルを差し替える運用とする（利用者からの依頼、2026-09-19）。 */}
        <img
          src="/help/ai-connect-step2-issue-token.png"
          alt={t('settings.aiConnection.guide.step2ScreenshotAlt')}
          className="mt-1 max-w-full rounded border border-gray-200"
        />
      </div>

      <p className="font-medium text-gray-900">{t('settings.aiConnection.guide.step3Title')}</p>
      <p className="font-medium text-gray-900">{t('settings.aiConnection.guide.step4Title')}</p>

      <div className="rounded-md bg-white p-2">
        <p className="font-medium text-gray-900">
          {t('settings.aiConnection.guide.whatIsPatTitle')}
        </p>
        <p className="text-xs text-gray-600">
          {t('settings.aiConnection.guide.whatIsPatDescription')}
        </p>
      </div>
    </div>
  )
}
