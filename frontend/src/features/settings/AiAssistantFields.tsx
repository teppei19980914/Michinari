/** 用途ごとのアシスタント選択（仕様書6.11、Phase7完了条件「アシスタントが用途ごとに
 * 一覧から選択できる（識別子の手入力を求めない）」）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた AiConnectionSection
 * から切り出したものである。用途と選択欄の対応が崩れても画面には同じ形の選択欄が並ぶだけで
 * 気づけないため、用途の一覧は assistantFields.ts に集約し、変更の通知は用途（フィールド名）を
 * 添えて返す。 */
import { t } from '../../locales/t'
import type { AiAssistantRead } from '../../api/ai'
import type { AppSettingsRead } from '../../api/settings'
import { ASSISTANT_FIELDS, type AssistantUidField } from './assistantFields'

type AiConnection = AppSettingsRead['ai_connection']

export function AiAssistantFields({
  values,
  assistants,
  onChange,
}: {
  values: AiConnection
  assistants: AiAssistantRead[] | undefined
  /** どの用途の選択が変わったかを添えて返す。用途を取り違えないよう呼び出し側で書き込む。 */
  onChange: (field: AssistantUidField, uid: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {ASSISTANT_FIELDS.map(({ field, labelKey }) => (
        <label key={field} className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t(labelKey)}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={values[field]}
            onChange={(e) => onChange(field, e.target.value)}
          >
            {!values[field] && <option value="">{t('common.unset')}</option>}
            {assistants?.map((assistant) => (
              <option key={assistant.uid} value={assistant.uid}>
                {assistant.name}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  )
}
