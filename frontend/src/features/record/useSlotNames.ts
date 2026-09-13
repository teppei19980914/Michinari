import { useQuery } from '@tanstack/react-query'
import { listSlots } from '../../api/resources'

/** 「他の時間枠を追加」の候補となる全時間枠（slot_id → 名称）。
 * 配分していない枠でも実績は記録できる（仕様書6.5「未配分スロットの追加」）。
 *
 * SC-06（DailyReportPage）とSC-07（ProgressOnlyPage）で同じものが必要なため共通化する
 * （CODING_RULES.md「①DRYの原則」）。
 *
 * この取得は画面のローディング判定には含めない。時間枠の名称は「他の時間枠を追加」の
 * 選択肢を埋めるための補助情報にすぎず、取得できなくても空のMapとして実績入力は続行できる
 * ため、ここで待たせると入力開始が不必要に遅れる。 */
export function useSlotNames(): Map<number, string> {
  const query = useQuery({ queryKey: ['resource-slots'], queryFn: listSlots })
  return new Map((query.data ?? []).map((slot) => [slot.id, slot.name]))
}
