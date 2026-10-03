import { t } from '../locales/t'
import { SlotList } from '../features/resource/SlotList'
import { DayTypeDefaultsCard } from '../features/resource/DayTypeDefaultsCard'
import { DayBoundaryHourCard } from '../features/resource/DayBoundaryHourCard'
import { AllocationStatusCard } from '../features/resource/AllocationStatusCard'

/** SC-04 リソースマスタ設定（仕様書6.3）。 */
export function ResourceSettingsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('resources.title')}</h1>
      <SlotList />
      <DayTypeDefaultsCard />
      <DayBoundaryHourCard />
      <AllocationStatusCard />
    </div>
  )
}
