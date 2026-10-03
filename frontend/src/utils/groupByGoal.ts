type GoalAttributed = { goal_id: number; goal_name: string }

export type GoalGroup<T> = {
  goalId: number
  goalName: string
  items: T[]
}

/** 目標IDでグルーピングする（最初に出現した目標の順序を保つ）。ダッシュボードの
 * 「本日のノルマ」と日次報告の実績入力欄は、複数目標の教材が1つの一覧に混在するため、
 * 目標名での表示グルーピングに共用する（CLAUDE.md DRYの原則）。 */
export function groupByGoal<T extends GoalAttributed>(items: T[]): GoalGroup<T>[] {
  const groups: GoalGroup<T>[] = []
  const groupByGoalId = new Map<number, GoalGroup<T>>()

  for (const item of items) {
    let group = groupByGoalId.get(item.goal_id)
    if (!group) {
      group = { goalId: item.goal_id, goalName: item.goal_name, items: [] }
      groupByGoalId.set(item.goal_id, group)
      groups.push(group)
    }
    group.items.push(item)
  }

  return groups
}
