/**
 * リプラン履歴タブ。PlanBaselineRead（Phase3で実装済みのGET /goals/{id}/baselinesをそのまま
 * 再利用）は「その時点のノルマ」のみを持ち「変更前ノルマ」は持たないため、教材ごとに
 * effective_from昇順で並べ、直前レコードのbaseline_daily_quotaを「変更前ノルマ」として
 * 補って1行にする（仕様書6.8「変更前後のノルマ」）。
 */

export type PlanBaselineInput = {
  id: number
  material_id: number
  effective_from: string
  baseline_daily_quota: number
  reason: string
}

export type ReplanHistoryRow = {
  id: number
  materialId: number
  materialName: string
  effectiveFrom: string
  reason: string
  quotaBefore: number | null
  quotaAfter: number
}

export function buildReplanHistoryRows(
  baselines: PlanBaselineInput[],
  materialNameById: Map<number, string>,
): ReplanHistoryRow[] {
  const byMaterial = new Map<number, PlanBaselineInput[]>()
  for (const baseline of baselines) {
    const list = byMaterial.get(baseline.material_id) ?? []
    list.push(baseline)
    byMaterial.set(baseline.material_id, list)
  }

  const rows: ReplanHistoryRow[] = []
  for (const [materialId, list] of byMaterial) {
    const chronological = [...list].sort(
      (a, b) => a.effective_from.localeCompare(b.effective_from) || a.id - b.id,
    )
    chronological.forEach((entry, index) => {
      rows.push({
        id: entry.id,
        materialId,
        materialName: materialNameById.get(materialId) ?? String(materialId),
        effectiveFrom: entry.effective_from,
        reason: entry.reason,
        quotaBefore: index === 0 ? null : chronological[index - 1].baseline_daily_quota,
        quotaAfter: entry.baseline_daily_quota,
      })
    })
  }

  return rows.sort(
    (a, b) => b.effectiveFrom.localeCompare(a.effectiveFrom) || b.id - a.id,
  )
}
