import type { GoalRead } from '../../api/goals'
import { t } from '../../locales/t'

type GoalTabBarProps = {
  goals: GoalRead[]
  selectedGoalId: number | null
  onSelect: (goalId: number) => void
}

/** 目標単位のタブ切り替えUI（DashboardPage・CalendarPage・AnalyticsPage・DailyReportPage・
 * DailyReportViewPage共通、CLAUDE.md DRYの原則）。カテゴリ名＋目標名をタブラベルとする。
 * アーカイブ済みの目標を並べうるのは分析（SC-09、アーカイブ表示トグルON時）のみのため、
 * 通常表示と区別できるよう目標名の後にアーカイブ済みである旨を添える（仕様書6.8）。
 *
 * `GlobalNav`の開閉に連動してstickyのtop位置を詰める（UIリッチ化、`--subheader-offset`は
 * `useHeaderVisibility`のProviderがCSS変数として配信する。二重のscroll購読を避けるため
 * ここでは直接scrollを監視せずCSS変数を参照するだけにしている）。 */
export function GoalTabBar({ goals, selectedGoalId, onSelect }: GoalTabBarProps) {
  return (
    <div className="sticky top-[var(--subheader-offset)] z-10 flex gap-1 overflow-x-auto border-b border-border bg-surface transition-[top] duration-200 ease-in-out">
      {goals.map((goal) => (
        <button
          key={goal.id}
          type="button"
          onClick={() => onSelect(goal.id)}
          className={`whitespace-nowrap px-3 py-2 text-sm font-medium ${
            selectedGoalId === goal.id
              ? 'border-b-2 border-accent text-accent-muted-text'
              : 'text-text-faint hover:text-text-muted'
          }`}
        >
          {t(`goals.new.category.${goal.category}`)}
          {' ・ '}
          {goal.name}
          {goal.archived_at !== null && ` ・ ${t('goals.list.archivedBadge')}`}
        </button>
      ))}
    </div>
  )
}
