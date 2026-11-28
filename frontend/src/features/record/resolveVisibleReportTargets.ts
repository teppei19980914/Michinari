import type {
  ActiveReadingBook,
  ActiveWorkAssignment,
  BookRead,
  GoalRead,
  WorkAssignmentRead,
} from '../../api/goals'
import type { GoalScheduleItemsForReportRead, QuotaItemRead } from '../../api/records'
import type { CategoryPresence } from './categoryCompletion'
import { isSectionVisible } from './sectionVisibility'

export type VisibleReportTargetsInput = {
  /** 目標タブを表示しているか（着手中の目標が2件以上。useGoalReportTabs）。 */
  showGoalSelector: boolean
  /** タブで選択中の目標。タブ非表示のときはundefined。 */
  selectedGoal: GoalRead | undefined
  /** 全目標。ACTIVEな資格試験目標（日記の対象）をここから絞り込む。 */
  goals: GoalRead[]
  quotaItems: QuotaItemRead[]
  readingBooks: ActiveReadingBook[]
  workAssignments: ActiveWorkAssignment[]
  /** 「今日の作業項目」欄の対象（開発Todo_スケジュール・ガントチャート_v1.1 第4章、単位4）。
   * GET /records/{date}/schedule-items の応答（3種別が混在）。 */
  scheduleItems: GoalScheduleItemsForReportRead[]
  /** 確定済みの種別向け「今日の作業項目」欄（軽微な修正3、開発Todo_スケジュール・
   * ガントチャート_検証修正_v1.0.md）。GET /records/{date}/schedule-items-history の応答。 */
  scheduleItemsHistory: GoalScheduleItemsForReportRead[]
}

export type VisibleReportTargets = {
  /** その日そのカテゴリに確定すべき目標があるか。選択中タブに関係なく判定する。 */
  presence: CategoryPresence
  quotaItems: QuotaItemRead[]
  diaryGoals: GoalRead[]
  books: BookRead[]
  workAssignments: WorkAssignmentRead[]
  examScheduleItemGoals: GoalScheduleItemsForReportRead[]
  readingScheduleItemGoals: GoalScheduleItemsForReportRead[]
  workScheduleItemGoals: GoalScheduleItemsForReportRead[]
  examScheduleItemHistoryGoals: GoalScheduleItemsForReportRead[]
  readingScheduleItemHistoryGoals: GoalScheduleItemsForReportRead[]
  workScheduleItemHistoryGoals: GoalScheduleItemsForReportRead[]
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

/** 「今日の作業項目」欄の対象をカテゴリごとに絞り込む（単位4、軽微な修正3）。
 * `scheduleItems`（ライブ）・`scheduleItemsHistory`（確定済みの種別向け）のいずれも
 * 3種別混在の同じ形で返るため、絞り込みロジックを共通化する（CLAUDE.md DRYの原則）。 */
function selectScheduleItemGoalsByCategory(
  input: Pick<VisibleReportTargetsInput, 'showGoalSelector' | 'selectedGoal'>,
  allGoalItems: GoalScheduleItemsForReportRead[],
): {
  exam: GoalScheduleItemsForReportRead[]
  reading: GoalScheduleItemsForReportRead[]
  work: GoalScheduleItemsForReportRead[]
} {
  const byCategory = (category: GoalRead['category']) =>
    allGoalItems.filter((goalItems) => goalItems.goal_category === category)
  const examAll = byCategory('EXAM')
  const readingAll = byCategory('READING')
  const workAll = byCategory('WORK')
  return {
    exam: selectForCategory(input, 'EXAM', examAll, (goal) =>
      examAll.filter((goalItems) => goalItems.goal_id === goal.id),
    ),
    reading: selectForCategory(input, 'READING', readingAll, (goal) =>
      readingAll.filter((goalItems) => goalItems.goal_id === goal.id),
    ),
    work: selectForCategory(input, 'WORK', workAll, (goal) =>
      workAll.filter((goalItems) => goalItems.goal_id === goal.id),
    ),
  }
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
  // 日記（DiaryFields）は資格試験の複数目標混同対策（未決事項L-04）が目的のため、対象は
  // ACTIVEな資格試験目標のみに限定する。読書目標は想起（ReadingLogFields）が同じ役割を
  // 果たすため、両方の入力欄が並ぶ重複を避ける。
  const activeGoals = input.goals.filter(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )
  const activeBooks = input.readingBooks.map((entry) => entry.book)
  const activeWorkAssignments = input.workAssignments.map((entry) => entry.workAssignment)

  const quotaItems = selectForCategory(input, 'EXAM', input.quotaItems, (goal) =>
    input.quotaItems.filter((item) => item.goal_id === goal.id),
  )
  const diaryGoals = selectForCategory(input, 'EXAM', activeGoals, (goal) => [goal])
  const books = selectForCategory(input, 'READING', activeBooks, (goal) =>
    input.readingBooks.filter((entry) => entry.goal.id === goal.id).map((entry) => entry.book),
  )
  const workAssignments = selectForCategory(input, 'WORK', activeWorkAssignments, (goal) =>
    input.workAssignments
      .filter((entry) => entry.goal.id === goal.id)
      .map((entry) => entry.workAssignment),
  )

  // 「今日の作業項目」欄の対象（単位4、軽微な修正3）。ライブ・確定済み向けの両方を
  // 同じ絞り込みロジックで処理する。
  const scheduleItemGoals = selectScheduleItemGoalsByCategory(input, input.scheduleItems)
  const scheduleItemHistoryGoals = selectScheduleItemGoalsByCategory(
    input,
    input.scheduleItemsHistory,
  )

  return {
    // 「表示中か」ではなく「対象の目標があるか」で判定する。選択中でないタブのカテゴリを
    // 「対象なし」と誤判定すると、1カテゴリ確定しただけで全確定とみなしてしまう。
    presence: {
      hasExamCategory: activeGoals.length > 0,
      hasReadingCategory: activeBooks.length > 0,
      hasWorkCategory: activeWorkAssignments.length > 0,
    },
    quotaItems,
    diaryGoals,
    books,
    workAssignments,
    examScheduleItemGoals: scheduleItemGoals.exam,
    readingScheduleItemGoals: scheduleItemGoals.reading,
    workScheduleItemGoals: scheduleItemGoals.work,
    examScheduleItemHistoryGoals: scheduleItemHistoryGoals.exam,
    readingScheduleItemHistoryGoals: scheduleItemHistoryGoals.reading,
    workScheduleItemHistoryGoals: scheduleItemHistoryGoals.work,
    // 資格試験は教材（ノルマ）が無くても日記を書けるため、表示対象の有無ではなく目標の有無で
    // 判定する。読書・仕事は対象（書籍・案件）が無ければ入力も確定もできないため中身で判定する。
    showExamSection: isSectionVisible(input, 'EXAM', activeGoals.length > 0),
    showReadingSection: isSectionVisible(input, 'READING', books.length > 0),
    showWorkSection: isSectionVisible(input, 'WORK', workAssignments.length > 0),
  }
}
