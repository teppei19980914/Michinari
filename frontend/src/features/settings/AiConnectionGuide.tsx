import { t } from '../../locales/t'

/**
 * AI接続手順の段階的な案内（仕様書6.11、非エンジニア向けエラー表示改善2026-09-19）。
 *
 * 「NewtonX Web版を開く」のリンク先は、接続先URL（Host、例: xxx.newton-x.net）を
 * そのまま使う。固定のURLを持たない（所属ごとにサブドメインが異なるため、HelpPage
 * 6.13節のFAQ参照）。Hostが未入力のうちはリンクではなく案内文のみを表示する。
 *
 * 初回手順とトラブルシューティング（PATの再生成、2026-10-16追加）の2つを`<details>`で
 * アコーディオン化している（内容量の増加に伴う可読性対応、利用者からの依頼）。初回手順は
 * 初めて設定する利用者がすぐ見られるよう既定で開き、トラブルシューティングは普段は不要な
 * ため既定で閉じる。他の画面の折りたたみ表示（例: ChatPanel.tsxの文脈カテゴリ）と同じ
 * ネイティブ`<details>`を使う（CODING_RULES.md DRYの原則、新規ライブラリを増やさない）。
 */
export function AiConnectionGuide({ host }: { host: string }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-accent-disabled bg-accent-muted-bg p-3 text-sm text-text-secondary">
      <details open>
        <summary className="cursor-pointer select-none font-medium text-text-primary">
          {t('settings.aiConnection.guide.setupSectionTitle')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <div>
            <p className="font-medium text-text-primary">
              {t('settings.aiConnection.guide.step1Title')}
            </p>
            {host ? (
              <a
                className="text-accent-muted-text underline"
                href={`https://${host}`}
                target="_blank"
                rel="noreferrer"
              >
                {t('settings.aiConnection.guide.step1LinkLabel')}
              </a>
            ) : (
              <p className="text-xs text-text-faint">
                {t('settings.aiConnection.guide.step1HostMissing')}
              </p>
            )}
          </div>

          <div>
            <p className="font-medium text-text-primary">
              {t('settings.aiConnection.guide.step2Title')}
            </p>
            <p>{t('settings.aiConnection.guide.step2Description')}</p>
            {/* ダミー画像。実際のスクリーンショットは後で frontend/public/help/ 配下の
                同名ファイルを差し替える運用とする（利用者からの依頼、2026-09-19）。 */}
            <img
              src="/help/ai-connect-step2-issue-token.png"
              alt={t('settings.aiConnection.guide.step2ScreenshotAlt')}
              className="mt-1 max-w-full rounded border border-border"
            />
          </div>

          <p className="font-medium text-text-primary">
            {t('settings.aiConnection.guide.step3Title')}
          </p>
          <p className="font-medium text-text-primary">
            {t('settings.aiConnection.guide.step4Title')}
          </p>

          <div className="rounded-md bg-surface p-2">
            <p className="font-medium text-text-primary">
              {t('settings.aiConnection.guide.whatIsPatTitle')}
            </p>
            <p className="text-xs text-text-muted">
              {t('settings.aiConnection.guide.whatIsPatDescription')}
            </p>
          </div>
        </div>
      </details>

      <details>
        <summary className="cursor-pointer select-none font-medium text-text-primary">
          {t('settings.aiConnection.guide.troubleshootingSectionTitle')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <p>{t('settings.aiConnection.guide.troubleshootingDescription')}</p>

          <div>
            <p className="font-medium text-text-primary">
              {t('settings.aiConnection.guide.troubleshootingStep1Title')}
            </p>
            <p>{t('settings.aiConnection.guide.troubleshootingStep1Description')}</p>
          </div>

          <div>
            <p className="font-medium text-text-primary">
              {t('settings.aiConnection.guide.troubleshootingStep2Title')}
            </p>
            <p>{t('settings.aiConnection.guide.troubleshootingStep2Description')}</p>
          </div>

          <p className="font-medium text-text-primary">
            {t('settings.aiConnection.guide.troubleshootingStep3Title')}
          </p>
        </div>
      </details>
    </div>
  )
}
