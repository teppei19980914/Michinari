/** ウィザードの各ステップからバックエンドへ反映する処理をまとめる。
 *
 * ウィザードは「戻る」で内容を編集できるため、科目・教材は前回このステップで作成済みの
 * ものがあれば全て削除してから作り直す（更新の差分計算を避けるための単純な設計。
 * 件数は少数のため性能上の問題にはならない）。 */
import { t } from '../../../locales/t'
import {
  createMaterial,
  createSubject,
  deleteMaterial,
  deleteSubject,
  type MaterialRead,
  type SubjectRead,
} from '../../../api/goals'
import { createSlot } from '../../../api/resources'
import { updateSlotAllocations } from '../../../api/goals'
import {
  buildMaterialCreatePayload,
  buildSubjectCreatePayload,
  type ExamMaterialDraft,
  type ExamSubjectDraft,
} from './examWizardDrafts'
import { resolveWeekdaySlotTimes, resolveWeekendSlotTimes } from './simpleTimeSlots'

const WEEKDAY_WEEKDAYS = [0, 1, 2, 3, 4]
const WEEKEND_WEEKDAYS = [5, 6]

export async function replaceSubjects(
  goalId: number,
  subjects: ExamSubjectDraft[],
  previousIds: number[],
): Promise<SubjectRead[]> {
  for (const id of previousIds) {
    await deleteSubject(id)
  }
  const created: SubjectRead[] = []
  for (const draft of subjects) {
    created.push(await createSubject(goalId, buildSubjectCreatePayload(draft)))
  }
  return created
}

export async function replaceMaterials(
  goalId: number,
  materials: ExamMaterialDraft[],
  previousIds: number[],
  subjectIdByName: Record<string, number>,
  startDate: string,
): Promise<MaterialRead[]> {
  for (const id of previousIds) {
    await deleteMaterial(id)
  }
  const created: MaterialRead[] = []
  for (const draft of materials) {
    created.push(
      await createMaterial(goalId, buildMaterialCreatePayload(draft, subjectIdByName, startDate)),
    )
  }
  return created
}

/** スロットが1件も無い場合の簡易時間設定（仕様書「簡易時間設定からスロットへの変換」）。
 * 平日・休日それぞれ0時間より大きい入力があった分だけスロットを新規作成し、作成した
 * スロットの全時間をこの目標へ配分する（このために新規作成したスロットのため）。
 *
 * 環境タグは`PC`（机上のみ）を使う。`resource_slot.environment`はスロット自体の性質を
 * 表す列であり`ANY`（制約なし）を許容しない（`resource_service._validate_slot_fields`、
 * データ構造編5.2「TEXT NOT NULL Environment（PC / MOBILE）」）。`ANY`は教材側の
 * 「必要環境を問わない」を表す値であり、スロット側とは意味が異なる。実機での動作確認
 * （`POST /resources/slots`）で`environment: 'ANY'`がVALIDATION_ERRORになることを発見し
 * 是正した。教材側の既定値`required_environment: 'ANY'`（examWizardDrafts.ts）とは
 * 矛盾なく両立する（ANYは「机上のみでも移動中でもよい」という制約無しを意味するため）。 */
export async function createAndAllocateSimpleSlots(
  goalId: number,
  weekdayHours: number,
  weekendHours: number,
): Promise<void> {
  const allocations: { slot_id: number; minutes: number }[] = []

  if (weekdayHours > 0) {
    const times = resolveWeekdaySlotTimes(weekdayHours)
    const slot = await createSlot({
      name: t('goals.examWizard.step4.weekdaySlotName'),
      start_time: times.startTime,
      end_time: times.endTime,
      environment: 'PC',
      weekdays: WEEKDAY_WEEKDAYS,
    })
    allocations.push({ slot_id: slot.id, minutes: weekdayHours * 60 })
  }

  if (weekendHours > 0) {
    const times = resolveWeekendSlotTimes(weekendHours)
    const slot = await createSlot({
      name: t('goals.examWizard.step4.weekendSlotName'),
      start_time: times.startTime,
      end_time: times.endTime,
      environment: 'PC',
      weekdays: WEEKEND_WEEKDAYS,
    })
    allocations.push({ slot_id: slot.id, minutes: weekendHours * 60 })
  }

  if (allocations.length > 0) {
    await updateSlotAllocations(goalId, { allocations })
  }
}
