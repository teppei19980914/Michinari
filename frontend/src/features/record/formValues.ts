/**
 * 「id ごとの入力値」を保持する下書きstateの1項目だけを書き換えた新しい値を返す。
 *
 * 実績入力の下書きは教材id・書籍id・案件id・目標idをキーにしたオブジェクトで保持しており、
 * 1項目の変更は「対象idのオブジェクトだけ差し替えた新しいオブジェクト」を作る必要がある。
 * この入れ子の組み立てが日次報告（SC-06）と進捗のみ登録（SC-07）で計8箇所に複製されていた
 * （CODING_RULES.md「①DRYの原則」）。
 *
 * フィールド名と値を型引数で結び付けているため、対象の型に無いフィールド名や、型の合わない
 * 値を渡すとコンパイルエラーになる。
 *
 * @param current 現在の下書き（id → 入力値）
 * @param id 書き換える対象のid
 * @param field 書き換えるフィールド
 * @param value 新しい値
 * @returns 対象idの該当フィールドだけを差し替えた新しい下書き
 */
export function patchFormValue<V, K extends keyof V>(
  current: Record<number, V>,
  id: number,
  field: K,
  value: V[K],
): Record<number, V> {
  return { ...current, [id]: { ...current[id], [field]: value } }
}
