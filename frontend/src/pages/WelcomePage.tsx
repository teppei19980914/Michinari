import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { QuickCreateGoalModal } from '../features/goal/QuickCreateGoalModal'

/** SC-16 ウェルカム画面（仕様書「初回起動時のウェルカム画面」）。
 *
 * 目標が0件の状態では`DashboardPage`からここへリダイレクトされる。既存ユーザや
 * 開発者が使い方を再確認できるよう、目標の有無に関わらずいつでも訪問できる独立ルート
 * （`/welcome`）とし、ヘルプ画面（SC-14）からも再アクセスできる導線を設けている。 */
export function WelcomePage() {
  const navigate = useNavigate()
  const [quickCreateCategory, setQuickCreateCategory] = useState<'READING' | 'WORK' | null>(null)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <p className="text-sm text-gray-700">{t('welcome.appIntro')}</p>
      <h1 className="text-xl font-semibold text-gray-900">{t('welcome.heading')}</h1>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <button type="button" className="text-left" onClick={() => setQuickCreateCategory('READING')}>
          <Card className="flex h-full flex-col gap-1 hover:border-blue-300">
            <span className="text-xs font-medium text-blue-600">{t('welcome.reading.recommended')}</span>
            <span className="font-medium text-gray-900">{t('welcome.reading.title')}</span>
            <span className="text-sm text-gray-600">{t('welcome.reading.description')}</span>
          </Card>
        </button>

        <button type="button" className="text-left" onClick={() => setQuickCreateCategory('WORK')}>
          <Card className="flex h-full flex-col gap-1 hover:border-blue-300">
            <span className="font-medium text-gray-900">{t('welcome.work.title')}</span>
            <span className="text-sm text-gray-600">{t('welcome.work.description')}</span>
          </Card>
        </button>

        <button type="button" className="text-left" onClick={() => navigate(ROUTES.goalNewExam)}>
          <Card className="flex h-full flex-col gap-1 hover:border-blue-300">
            <span className="font-medium text-gray-900">{t('welcome.exam.title')}</span>
            <span className="text-sm text-gray-600">{t('welcome.exam.description')}</span>
            <span className="text-xs text-gray-400">{t('welcome.exam.note')}</span>
          </Card>
        </button>
      </div>

      <div className="flex justify-end">
        <Button variant="secondary" onClick={() => navigate(ROUTES.dashboard)}>
          {t('welcome.later')}
        </Button>
      </div>

      <QuickCreateGoalModal
        // キャンセル後の再オープンや種別の切り替え時に前回の入力が残らないよう、
        // 開閉のたびに別インスタンスとして作り直す（QuickCreateGoalModal自身は
        // onSuccess時にしか入力をクリアしないため）。
        key={quickCreateCategory ?? 'closed'}
        open={quickCreateCategory !== null}
        category={quickCreateCategory ?? 'READING'}
        onClose={() => setQuickCreateCategory(null)}
        onCreated={() => navigate(ROUTES.dashboard, { state: { showFirstRecordBanner: true } })}
      />
    </div>
  )
}
