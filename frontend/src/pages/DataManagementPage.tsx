import { t } from '../locales/t'
import { Card } from '../components/Card'
import { Button } from '../components/Button'

/**
 * SC-12 データ管理（仕様書6.12）。エクスポート/インポート/バックアップの実処理は
 * 実装フェーズ分割計画書Phase10の担当のため、本フェーズではPhase6のComingSoonPageと同様に
 * 遷移経路のみ確立し、各操作はプレースホルダーとする。
 */
export function DataManagementPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('dataManagement.title')}</h1>
      <p className="text-sm text-gray-500">{t('dataManagement.notice')}</p>
      <Card className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled>
          {t('dataManagement.export')}
        </Button>
        <Button variant="secondary" disabled>
          {t('dataManagement.import')}
        </Button>
        <Button variant="secondary" disabled>
          {t('dataManagement.backup')}
        </Button>
      </Card>
    </div>
  )
}
