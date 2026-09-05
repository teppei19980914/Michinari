import type { GoalRead } from '../../api/goals'
import { t } from '../../locales/t'

type GoalTabBarProps = {
  goals: GoalRead[]
  selectedGoalId: number | null
  onSelect: (goalId: number) => void
}

/** 目標単位のタブ切り替えUI（DailyReportPage・DailyReportViewPage共通、CLAUDE.md
 * DRYの原則）。カテゴリ名＋目標名をタブラベルとする。 */
export function GoalTabBar({ goals, selectedGoalId, onSelect }: GoalTabBarProps) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-gray-200">
      {goals.map((goal) => (
        <button
          key={goal.id}
          type="button"
          onClick={() => onSelect(goal.id)}
          className={`whitespace-nowrap px-3 py-2 text-sm font-medium ${
            selectedGoalId === goal.id
              ? 'border-b-2 border-blue-600 text-blue-700'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {t(`goals.new.category.${goal.category}`)}
          {' ・ '}
          {goal.name}
        </button>
      ))}
    </div>
  )
}
