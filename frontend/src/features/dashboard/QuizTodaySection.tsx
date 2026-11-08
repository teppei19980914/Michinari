import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { ROUTES } from '../../constants/routes'

/** 今日の復習クイズの件数（開発Todo_復習クイズ_v1.0、仕様書6.1.6）。目標に紐づかない
 * アプリ全体の値のため、目標タブの切り替えの影響を受けない。0件の場合は表示しない。 */
export function QuizTodaySection({ count }: { count: number }) {
  if (count === 0) {
    return null
  }

  return (
    <Card className="flex items-center justify-between gap-3">
      <div>
        <h2 className="font-medium text-text-primary">{t('quiz.dashboardTitle')}</h2>
        <p className="text-sm text-text-faint">{t('quiz.dashboardCount', { count })}</p>
      </div>
      <Link to={ROUTES.quiz}>
        <Button>{t('quiz.startButton')}</Button>
      </Link>
    </Card>
  )
}
