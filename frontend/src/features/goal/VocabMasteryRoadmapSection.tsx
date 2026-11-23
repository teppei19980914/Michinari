import { t } from '../../locales/t'
import type { RoadmapVocabMasteryRead } from '../../api/goals'
import { VocabMasteryBreakdownLine } from '../vocab/VocabMasteryBreakdownLine'

/** 道のりマップ（詳細版）の「用語の習得」欄（開発Todo_単語帳_v1.0 要件E E-U5）。山の図
 * （RoadmapDiagram・roadmapGeometry.ts）には手を入れず、その下に別枠で表示する。 */
export function VocabMasteryRoadmapSection({
  vocabMastery,
}: {
  vocabMastery: RoadmapVocabMasteryRead
}) {
  const ratio =
    vocabMastery.total_count > 0 ? vocabMastery.mastered_count / vocabMastery.total_count : 0

  return (
    <div className="mt-3 flex flex-col gap-1 border-t border-border-strong pt-3">
      <p className="text-sm font-medium text-text-primary">{t('goals.roadmap.vocabMastery.title')}</p>
      <p className="text-sm text-text-secondary">
        {t('goals.roadmap.vocabMastery.countLabel', {
          mastered: vocabMastery.mastered_count,
          total: vocabMastery.total_count,
        })}
      </p>
      <VocabMasteryBreakdownLine
        termMastered={vocabMastery.term_mastered_count}
        termTotal={vocabMastery.term_total_count}
        situationMastered={vocabMastery.situation_mastered_count}
        situationTotal={vocabMastery.situation_total_count}
      />
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.round(ratio * 100)}%` }}
        />
      </div>
      <p className="text-xs text-text-faint">
        {vocabMastery.remaining_to_next_milestone != null
          ? t('goals.roadmap.vocabMastery.remainingLabel', {
              count: vocabMastery.remaining_to_next_milestone,
            })
          : t('goals.roadmap.vocabMastery.allMilestonesReached')}
      </p>
    </div>
  )
}
