import { useNavigate } from 'react-router-dom'
import { Card } from './Card'
import { Button } from './Button'
import { t } from '../locales/t'
import { ROUTE_PATTERNS } from '../constants/routes'

/**
 * AI未設定の状態でAIを使う機能（フィードバック・レポート生成等）を開いたときに、
 * エラーの代わりに表示する案内（非エンジニア向けエラー表示改善、完了条件D）。
 * 記録・閲覧はAI未設定でも使えるため、エラー扱いにしない。
 */
export function AiUnconfiguredNotice() {
  const navigate = useNavigate()

  return (
    <Card className="flex flex-col gap-2 bg-gray-50">
      <p className="text-sm text-gray-700">{t('aiUnconfigured.message')}</p>
      <p className="text-xs text-gray-500">{t('aiUnconfigured.recordingStillWorks')}</p>
      <div>
        <Button variant="secondary" onClick={() => navigate(ROUTE_PATTERNS.settings)}>
          {t('aiUnconfigured.settingsButton')}
        </Button>
      </div>
    </Card>
  )
}
