import type {
  ActiveReadingBook,
  ActiveWorkAssignment,
  BookRead,
  GoalRead,
  WorkAssignmentRead,
} from '../../api/goals'
import type { QuotaItemRead } from '../../api/records'
import { isSectionVisible } from './sectionVisibility'

export type VisibleReportTargetsInput = {
  /** 目標タブを表示しているか（着手中の目標が2件以上。useGoalReportTabs）。 */
  showGoalSelector: boolean
  /** タブで選択中の目標。タブ非表示のときはundefined。 */
  selectedGoal: GoalRead | undefined
  /** ACTIVEな資格試験目標（日記の対象）。 */
  activeGoals: GoalRead[]
  quotaItems: QuotaItemRead[]
  readingBooks: ActiveReadingBook[]
  workAssignments: ActiveWorkAssignment[]
}

export type VisibleReportTargets = {
  quotaItems: QuotaItemRead[]
  diaryGoals: GoalRead[]
  books: BookRead[]
  workAssignments: WorkAssignmentRead[]
  showExamSection: boolean
  showReadingSection: boolean
  showWorkSection: boolean
}

/** 選択中のタブに対応する分だけを取り出す。
 * showGoalSelectorがfalse（着手中の目標が0〜1件）の間は、selectedGoalIdに関わらず常に全件を
 * そのまま表示する（従来の挙動を維持し、切替UIがある場合にのみ絞り込む）。 */
function selectForCategory<T>(
  input: Pick<VisibleReportTargetsInput, 'showGoalSelector' | 'selectedGoal'>,
  category: GoalRead['category'],
  allTargets: T[],
  pickForGoal: (goal: GoalRead) => T[],
): T[] {
  if (!input.showGoalSelector) {
    return allTargets
  }
  if (!input.selectedGoal || input.selectedGoal.category !== category) {
    return []
  }
  return pickForGoal(input.selectedGoal)
}

/**
 * 日次報告画面（SC-06）で「いま表示すべき対象」を決める純粋関数。
 *
 * 目標タブの選択状態に応じた絞り込みと、カテゴリセクションの表示可否をまとめる。従来は
 * コンポーネント内に3階層のネストした三項演算子が7本並んでおり、条件の読み取りが難しく
 * 検証もできなかった（CODING_RULES.md「保守性（複雑度）」「フロントの分岐は`.ts`へ切り出す」）。
 *
 * カテゴリごとに独立して確定する仕様変更（2026-09-05）に伴い、対象カテゴリの目標が存在
 * しない場合はそのセクション自体を表示しない。以前は資格試験のみ非選択時に無条件表示して
 * いたため、資格試験目標を持たない利用者にも空のセクションと確定ボタンが表示され、確定操作が
 * 必要になっていた。
 */
export function resolveVisibleReportTargets(
  input: VisibleReportTargetsInput,
): VisibleReportTargets {
  const activeBooks = input.readingBooks.map((entry) => entry.book)
  const activeWorkAssignments = input.workAssignments.map((entry) => entry.workAssignment)

  const quotaItems = selectForCategory(input, 'EXAM', input.quotaItems, (goal) =>
    input.quotaItems.filter((item) => item.goal_id === goal.id),
  )
  const diaryGoals = selectForCategory(input, 'EXAM', input.activeGoals, (goal) => [goal])
  const books = selectForCategory(input, 'READING', activeBooks, (goal) =>
    input.readingBooks.filter((entry) => entry.goal.id === goal.id).map((entry) => entry.book),
  )
  const workAssignments = selectForCategory(input, 'WORK', activeWorkAssignments, (goal) =>
    input.workAssignments
      .filter((entry) => entry.goal.id === goal.id)
      .map((entry) => entry.workAssignment),
  )

  return {
    quotaItems,
    diaryGoals,
    books,
    workAssignments,
    // 資格試験は教材（ノルマ）が無くても日記を書けるため、表示対象の有無ではなく目標の有無で
    // 判定する。読書・仕事は対象（書籍・案件）が無ければ入力も確定もできないため中身で判定する。
    showExamSection: isSectionVisible(input, 'EXAM', input.activeGoals.length > 0),
    showReadingSection: isSectionVisible(input, 'READING', books.length > 0),
    showWorkSection: isSectionVisible(input, 'WORK', workAssignments.length > 0),
  }
}
