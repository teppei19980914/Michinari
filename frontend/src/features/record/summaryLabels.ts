import type { ActiveReadingBook, ActiveWorkAssignment } from '../../api/goals'
import type { QuotaItemRead } from '../../api/records'
import type { MaterialLabel } from './StudyLogSummaryList'
import type { BookLabel } from './ReadingLogSummaryList'
import type { WorkAssignmentLabel } from './WorkLogSummaryList'

/**
 * 確定済み実績のサマリ表示に使う「id → 表示名」の対応を組み立てる。
 *
 * 実績（study_logs / reading_logs / work_logs）は教材id・書籍id・案件idしか持たないため、
 * 表示にはノルマ・書籍・案件の一覧から名称を引き当てる必要がある。この引き当ては日次報告
 * （SC-06）と日次報告閲覧（SC-08）で同一で、従来は両画面に同じ組み立てが書かれていた
 * （CODING_RULES.md「①DRYの原則」。表示項目を1つ増やすと2箇所の修正が必要だった）。
 */
export function buildMaterialLabels(quotaItems: QuotaItemRead[]): Map<number, MaterialLabel> {
  return new Map(
    quotaItems.map((item) => [
      item.material_id,
      {
        name: item.material_name,
        unitLabel: item.unit_label,
        qualityMetricType: item.quality_metric_type,
      },
    ]),
  )
}

export function buildBookLabels(readingBooks: ActiveReadingBook[]): Map<number, BookLabel> {
  return new Map(readingBooks.map((entry) => [entry.book.id, { title: entry.book.title }]))
}

export function buildWorkAssignmentLabels(
  workAssignments: ActiveWorkAssignment[],
): Map<number, WorkAssignmentLabel> {
  return new Map(
    workAssignments.map((entry) => [
      entry.workAssignment.id,
      { clientName: entry.workAssignment.client_name },
    ]),
  )
}
