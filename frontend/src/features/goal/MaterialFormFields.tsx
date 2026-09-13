/** 教材フォーム（MaterialsTab.tsx の MaterialForm）の入力欄を行ごとに分けた表示部品。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた MaterialForm から、
 * 入力欄の並びだけを切り出したものである。値の保持・送信内容の判定は MaterialForm 側に
 * 残し、ここは受け取った値を描画して変更を呼び出し元へ返すだけに徹する。
 *
 * 値と変更ハンドラを個別のpropsで受け取るのは、stateの持ち方を変えずに移設するためである
 * （features/record/StudyLogFields.tsx と同じ書き方）。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Tooltip } from '../../components/Tooltip'
import type { SubjectRead } from '../../api/goals'

/** 必要な環境・品質指標の選択肢。MaterialsTab.tsx と同じ値を二重に持たないため、
 * 定義はこのファイルへ置き MaterialForm 側から取り込む。 */
export const ENVIRONMENTS = ['ANY', 'PC', 'MOBILE'] as const
export const QUALITY_METRIC_TYPES = ['NONE', 'OBJECTIVE', 'SELF_SCORED', 'SUBJECTIVE'] as const

export type MaterialEnvironment = (typeof ENVIRONMENTS)[number]
export type MaterialQualityMetricType = (typeof QUALITY_METRIC_TYPES)[number]

const LABEL_CLASS = 'flex flex-1 flex-col gap-1 text-sm text-gray-700'
const SELECT_CLASS = 'rounded-md border border-gray-300 px-3 py-2 text-sm'

/** 単位・総量・予定周回（いずれも必須項目）。 */
export function MaterialAmountFields({
  unitLabel,
  onChangeUnitLabel,
  totalAmount,
  onChangeTotalAmount,
  plannedCycles,
  onChangePlannedCycles,
}: {
  unitLabel: string
  onChangeUnitLabel: (value: string) => void
  totalAmount: string
  onChangeTotalAmount: (value: string) => void
  plannedCycles: string
  onChangePlannedCycles: (value: string) => void
}) {
  return (
    <div className="flex gap-2">
      <label className={LABEL_CLASS}>
        {t('goals.materials.unitLabel')}
        <Input value={unitLabel} onChange={(e) => onChangeUnitLabel(e.target.value)} required />
      </label>
      <label className={LABEL_CLASS}>
        {t('goals.materials.totalAmountLabel')}
        <Input
          type="number"
          min={0}
          value={totalAmount}
          onChange={(e) => onChangeTotalAmount(e.target.value)}
          required
        />
      </label>
      <label className={LABEL_CLASS}>
        {t('goals.materials.plannedCyclesLabel')}
        <Input
          type="number"
          min={1}
          value={plannedCycles}
          onChange={(e) => onChangePlannedCycles(e.target.value)}
          required
        />
      </label>
    </div>
  )
}

/** 対象科目の選択（1つ以上選ばないと保存できない）。 */
export function MaterialSubjectsField({
  subjects,
  selectedIds,
  onToggle,
}: {
  subjects: SubjectRead[]
  selectedIds: number[]
  onToggle: (subjectId: number) => void
}) {
  return (
    <fieldset className="flex flex-col gap-1 text-sm text-gray-700">
      <legend>{t('goals.materials.subjectsLabel')}</legend>
      <div className="flex flex-wrap gap-3">
        {subjects.map((subject) => (
          <label key={subject.id} className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={selectedIds.includes(subject.id)}
              onChange={() => onToggle(subject.id)}
            />
            {subject.name}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/** 開始日と締切（手動指定の切り替え付き）。
 *
 * `autoDueDate` は手動指定がoffのときだけ案内として表示する。締切として実際に送る値は
 * MaterialForm 側が決めるため、ここでは表示以外に使わない。 */
export function MaterialScheduleFields({
  startDate,
  onChangeStartDate,
  dueDateIsManual,
  onChangeDueDateIsManual,
  dueDate,
  onChangeDueDate,
  autoDueDate,
}: {
  startDate: string
  onChangeStartDate: (value: string) => void
  dueDateIsManual: boolean
  onChangeDueDateIsManual: (value: boolean) => void
  dueDate: string
  onChangeDueDate: (value: string) => void
  autoDueDate: string | null
}) {
  return (
    <div className="flex gap-2">
      <label className={LABEL_CLASS}>
        {t('goals.materials.startDateLabel')}
        <Input
          type="date"
          value={startDate}
          onChange={(e) => onChangeStartDate(e.target.value)}
          required
        />
      </label>
      <label className={LABEL_CLASS}>
        <span className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={dueDateIsManual}
            onChange={(e) => onChangeDueDateIsManual(e.target.checked)}
          />
          {t('goals.materials.dueDateManualLabel')}
        </span>
        <Input
          type="date"
          value={dueDate}
          onChange={(e) => onChangeDueDate(e.target.value)}
          disabled={!dueDateIsManual}
        />
        {!dueDateIsManual && autoDueDate && (
          <p className="text-xs text-gray-500">
            {t('goals.materials.autoDueDatePreview', { dueDate: autoDueDate })}
          </p>
        )}
      </label>
    </div>
  )
}

/** 学習の条件（所要ブロック時間・必要な環境・品質指標）。いずれも任意項目。 */
export function MaterialConditionFields({
  requiredBlockMinutes,
  onChangeRequiredBlockMinutes,
  requiredEnvironment,
  onChangeRequiredEnvironment,
  qualityMetricType,
  onChangeQualityMetricType,
}: {
  requiredBlockMinutes: string
  onChangeRequiredBlockMinutes: (value: string) => void
  requiredEnvironment: MaterialEnvironment
  onChangeRequiredEnvironment: (value: MaterialEnvironment) => void
  qualityMetricType: MaterialQualityMetricType
  onChangeQualityMetricType: (value: MaterialQualityMetricType) => void
}) {
  return (
    <div className="flex gap-2">
      <label className={LABEL_CLASS}>
        {t('goals.materials.requiredBlockMinutesLabel')}
        <Input
          type="number"
          min={1}
          value={requiredBlockMinutes}
          onChange={(e) => onChangeRequiredBlockMinutes(e.target.value)}
        />
      </label>
      <label className={LABEL_CLASS}>
        {t('goals.materials.requiredEnvironmentLabel')}
        <select
          className={SELECT_CLASS}
          value={requiredEnvironment}
          onChange={(e) => onChangeRequiredEnvironment(e.target.value as MaterialEnvironment)}
        >
          {ENVIRONMENTS.map((value) => (
            <option key={value} value={value}>
              {t(`goals.materials.environment.${value}`)}
            </option>
          ))}
        </select>
      </label>
      <label className={LABEL_CLASS}>
        <Tooltip label={t('goals.materials.qualityMetricTypeTooltip')}>
          <span>{t('goals.materials.qualityMetricTypeLabel')}</span>
        </Tooltip>
        <select
          className={SELECT_CLASS}
          value={qualityMetricType}
          onChange={(e) => onChangeQualityMetricType(e.target.value as MaterialQualityMetricType)}
        >
          {QUALITY_METRIC_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`goals.materials.qualityMetricType.${value}`)}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
