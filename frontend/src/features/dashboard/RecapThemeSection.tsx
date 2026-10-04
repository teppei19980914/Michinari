import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { listRecapThemes } from '../../api/recap'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { ROUTES } from '../../constants/routes'

/** 振り返り（テーマ累積）のテーマ一覧（資格試験・読書の目標向け、仕様書6.1.3）。
 * 本文の更新が新しいテーマから並ぶ。タップすると詳細ページへ移動する。 */
export function RecapThemeSection({ goalId }: { goalId: number }) {
  const query = useQuery({
    queryKey: QUERY_KEYS.recapThemes(goalId),
    queryFn: () => listRecapThemes(goalId),
  })

  return (
    <Card>
      <h2 className="font-medium text-gray-900">{t('dashboard.recapThemes.title')}</h2>
      {query.isLoading && <p className="mt-1 text-sm text-gray-500">{t('common.loading')}</p>}
      {query.isError && <p className="mt-1 text-sm text-red-600">{apiErrorMessage(query.error)}</p>}
      {query.data && query.data.length === 0 && (
        <p className="mt-1 text-sm text-gray-500">{t('dashboard.recapThemes.empty')}</p>
      )}
      {query.data && query.data.length > 0 && (
        <ul className="mt-2 flex flex-col gap-2">
          {query.data.map((theme) => (
            <li key={theme.id} className="flex items-baseline justify-between gap-2">
              <Link className="text-sm font-medium text-blue-700 underline" to={ROUTES.recapTheme(theme.id)}>
                {theme.name}
              </Link>
              <span className="text-xs text-gray-500">
                {t('dashboard.recapThemes.entryCount', { count: theme.entry_count })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
