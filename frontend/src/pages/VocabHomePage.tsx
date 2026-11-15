import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { apiErrorMessage } from '../api/client'
import { listGoals } from '../api/goals'
import { QUERY_KEYS } from '../constants/queryKeys'

/** グローバルナビ「単語帳」の入口（開発Todo_単語帳_v1.0 要件A §0 D8）。単語帳は資格試験の
 * 目標にのみ紐づくため、まず資格試験の目標を選ばせ、各目標詳細の「単語帳」タブへ誘導する
 * （目標の状態に関わらず表示する、§0 U1）。 */
export function VocabHomePage() {
  const goalsQuery = useQuery({ queryKey: QUERY_KEYS.goals(), queryFn: listGoals })

  if (goalsQuery.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (goalsQuery.isError || !goalsQuery.data) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(goalsQuery.error)}</p>
  }

  const examGoals = goalsQuery.data.filter((goal) => goal.category === 'EXAM')

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-text-primary">{t('vocab.home.title')}</h1>
      <p className="text-sm text-text-faint">{t('vocab.home.description')}</p>

      {examGoals.length === 0 && <p className="text-sm text-text-faint">{t('vocab.home.empty')}</p>}

      {examGoals.map((goal) => (
        <Link key={goal.id} to={ROUTES.goalDetail(goal.id)}>
          <Card className="hover:bg-surface-muted">
            <p className="text-sm font-medium text-text-primary">{goal.name}</p>
          </Card>
        </Link>
      ))}
    </div>
  )
}
