/** 教材フォーム（MaterialsTab.tsx の MaterialForm）の入力値と、そこから作る送信内容。
 *
 * 「手動締切がoffなら入力済みの日付を送らない」「任意項目の空欄は空文字ではなく`null`で
 * 送る」といった判定は、壊れるとサーバへ誤った値が届く。フォームの状態保持（フック）から
 * 切り離して純粋関数に置き、単体テストで固定する（OPERATIONS.md「フロントエンドのテストと
 * カバレッジ」の「送信内容を決める判定を持つか」で線を引く方針）。 */
import type { MaterialCreate } from '../../api/goals'
import type { MaterialEnvironment, MaterialQualityMetricType } from './MaterialFormFields'

/** 教材フォームの入力値。数値項目も入力途中の状態を保てるよう文字列で持つ。 */
export interface MaterialFormValues {
  name: string
  unitLabel: string
  totalAmount: string
  plannedCycles: string
  subjectIds: number[]
  startDate: string
  dueDateIsManual: boolean
  dueDate: string
  requiredBlockMinutes: string
  requiredEnvironment: MaterialEnvironment
  qualityMetricType: MaterialQualityMetricType
}

/**
 * 入力値から作成・更新の送信内容を組み立てる（作成と更新で同じ形）。
 *
 * 締切（`due_date`）は手動指定がonのときだけ入力欄の値を送る。offへ戻した場合、入力欄に
 * 日付が残っていてもサーバ側の自動導出に委ねるため`null`を送る。所要ブロック時間は任意
 * 項目のため、空欄は`0`ではなく`null`にする。
 */
export function buildMaterialPayload(values: MaterialFormValues): MaterialCreate {
  return {
    name: values.name,
    unit_label: values.unitLabel,
    total_amount: Number(values.totalAmount),
    planned_cycles: Number(values.plannedCycles),
    subject_ids: values.subjectIds,
    start_date: values.startDate,
    due_date_is_manual: values.dueDateIsManual,
    due_date: values.dueDateIsManual ? values.dueDate || null : null,
    required_block_minutes:
      values.requiredBlockMinutes === '' ? null : Number(values.requiredBlockMinutes),
    required_environment: values.requiredEnvironment,
    quality_metric_type: values.qualityMetricType,
  }
}
