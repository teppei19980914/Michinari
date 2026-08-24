import { t } from '../locales/t'

/** 後続フェーズで実装する画面のプレースホルダー（Phase6時点ではルーティングの疎通のみ確立する）。 */
export function ComingSoonPage({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
      <p className="mt-2 text-sm text-gray-500">{t('common.comingSoon')}</p>
    </div>
  )
}
