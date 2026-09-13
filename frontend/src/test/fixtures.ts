/** 描画テスト用のAPIレスポンス組み立て（Phase 34）。
 *
 * `GoalDetailRead` などの自動生成型は必須項目が多く、各テストで丸ごと書くと
 * 「そのテストが何を意図しているか」がフィクスチャの中に埋もれる。既定値を1箇所へ置き、
 * 各テストは検証したい項目だけを上書きする（CODING_RULES.md ①DRYの原則）。
 *
 * 値は「型を満たす無難な既定値」であり、特定の仕様を表すものではない。仕様上の意味を
 * 持たせたい値は、必ず呼び出し側で明示的に上書きすること。 */
import type {
  BookRead,
  GoalDetailRead,
  GoalRead,
  LoadProfileRead,
  MaterialRead,
  SlotAllocationRead,
  SubjectRead,
  WorkAssignmentRead,
} from '../api/goals'
import type { WorkReportRead } from '../api/closure'
import type { DashboardRead } from '../api/dashboard'

/** 既定の目標ID。個別の値に意味はないが、取り違えを見つけやすいよう各IDはずらしてある。 */
export const GOAL_ID = 1
export const SUBJECT_ID = 11
export const MATERIAL_ID = 21
export const BOOK_ID = 31
export const LOAD_PROFILE_ID = 41
export const SLOT_ID = 51
export const WORK_ASSIGNMENT_ID = 61
export const WORK_REPORT_ID = 71
export const MONTHLY_PERIOD_KEY = '2026-09'

export function makeSubject(overrides: Partial<SubjectRead> = {}): SubjectRead {
  return {
    id: SUBJECT_ID,
    goal_id: GOAL_ID,
    name: '科目A',
    exam_date_type: 'FIXED',
    exam_date_from: null,
    exam_date_to: null,
    exam_date_fixed: '2026-12-01',
    passing_score: null,
    passing_score_type: 'PERCENTAGE',
    passing_score_max: null,
    display_order: 1,
    ...overrides,
  }
}

export function makeMaterial(overrides: Partial<MaterialRead> = {}): MaterialRead {
  return {
    id: MATERIAL_ID,
    goal_id: GOAL_ID,
    name: '教材A',
    unit_label: '問',
    total_amount: 100,
    planned_cycles: 1,
    subject_ids: [SUBJECT_ID],
    start_date: '2026-09-01',
    due_date: '2026-11-30',
    due_date_is_manual: false,
    required_block_minutes: null,
    required_environment: 'ANY',
    quality_metric_type: 'NONE',
    is_active: true,
    display_order: 1,
    total_work: 100,
    current_cycle: 1,
    remaining: 100,
    completed: 0,
    progress_rate_in_cycle: 0,
    progress_rate: 0,
    ...overrides,
  }
}

export function makeBook(overrides: Partial<BookRead> = {}): BookRead {
  return {
    id: BOOK_ID,
    goal_id: GOAL_ID,
    title: '書籍A',
    author: '著者A',
    total_pages: 300,
    start_date: '2026-09-01',
    due_date: '2026-11-30',
    remaining_days: 78,
    last_reading_date: '2026-09-12',
    current_streak: 3,
    current_page: 60,
    progress_rate: 0.2,
    ...overrides,
  }
}

export function makeLoadProfile(overrides: Partial<LoadProfileRead> = {}): LoadProfileRead {
  return {
    id: LOAD_PROFILE_ID,
    goal_id: GOAL_ID,
    date_from: '2026-10-01',
    date_to: '2026-10-31',
    coefficient: 1.5,
    note: '繁忙期',
    ...overrides,
  }
}

export function makeSlotAllocation(
  overrides: Partial<SlotAllocationRead> = {},
): SlotAllocationRead {
  return {
    slot_id: SLOT_ID,
    slot_name: '朝の枠',
    environment: 'ANY',
    // 月〜金（`resources.weekdays.*` のキーに対応する 0=月 始まりの番号）。
    weekdays: [0, 1, 2, 3, 4],
    duration_minutes: 60,
    minutes: 30,
    others_minutes: 10,
    is_over_capacity: false,
    ...overrides,
  }
}

export function makeWorkAssignment(
  overrides: Partial<WorkAssignmentRead> = {},
): WorkAssignmentRead {
  return {
    id: WORK_ASSIGNMENT_ID,
    goal_id: GOAL_ID,
    client_name: '取引先A',
    expected_content: '期待される成果の説明',
    start_date: '2026-09-01',
    elapsed_days: 12,
    last_work_date: '2026-09-12',
    current_streak: 3,
    has_recent_monthly_report: true,
    ...overrides,
  }
}

export function makeWorkReport(overrides: Partial<WorkReportRead> = {}): WorkReportRead {
  return {
    id: WORK_REPORT_ID,
    goal_id: GOAL_ID,
    period_type: 'MONTHLY',
    period_key: MONTHLY_PERIOD_KEY,
    body: '# 月次報告 本文',
    target_goal_text: '当月の目標',
    business_summary: '業務内容の要約',
    achievement_score: 3,
    achievement_reflection: '振り返り',
    next_goal_text: '翌月の目標',
    report_notes: '特記事項',
    is_anonymized: false,
    generated_at: '2026-09-13T00:00:00',
    edited_at: null,
    ...overrides,
  }
}

/** ダッシュボード。目標ごとの配列は既定で GOAL_ID の1件だけを持つ。
 *
 * 複数目標の絞り込みを検証するテストは、`goal_cards` などを明示的に上書きして
 * 別 goal_id の要素を混ぜること。 */
export function makeDashboard(overrides: Partial<DashboardRead> = {}): DashboardRead {
  return {
    logical_date: '2026-09-13',
    record_state: null,
    today_day_type: 'PLAN',
    report_rate_window_days: 14,
    goal_cards: [makeGoalCard()],
    goal_stats: [makeGoalStats()],
    today_quota: [makeTodayQuotaEntry()],
    available_slot_names: ['朝の枠'],
    ...overrides,
  }
}

export function makeGoalCard(
  overrides: Partial<DashboardRead['goal_cards'][number]> = {},
): DashboardRead['goal_cards'][number] {
  return {
    goal_id: GOAL_ID,
    goal_name: '目標A',
    category: 'EXAM',
    progress_rate: 0.3,
    remaining_days: 80,
    forecast_deviation_days: 0,
    has_warning: false,
    has_forced_replan: false,
    ...overrides,
  }
}

export function makeGoalStats(
  overrides: Partial<DashboardRead['goal_stats'][number]> = {},
): DashboardRead['goal_stats'][number] {
  return {
    goal_id: GOAL_ID,
    goal_name: '目標A',
    consecutive_report_days: 3,
    recent_report_rate: 0.8,
    buffer_usage_rate: null,
    material_speeds: [],
    ...overrides,
  }
}

export function makeTodayQuotaEntry(
  overrides: Partial<DashboardRead['today_quota'][number]> = {},
): DashboardRead['today_quota'][number] {
  return {
    material_id: MATERIAL_ID,
    material_name: '教材A',
    current_cycle: 1,
    planned_cycles: 1,
    daily_quota: 10,
    unit_label: '問',
    target_minutes: 30,
    goal_id: GOAL_ID,
    goal_name: '目標A',
    ...overrides,
  }
}

export function makeGoal(overrides: Partial<GoalRead> = {}): GoalRead {
  return {
    id: GOAL_ID,
    category: 'EXAM',
    name: '目標A',
    start_date: '2026-09-01',
    status: 'ACTIVE',
    memo: null,
    activated_at: '2026-09-01T00:00:00',
    closed_at: null,
    archived_at: null,
    ...overrides,
  }
}

/** 目標詳細。共通する目標の項目は `makeGoal` から引き継ぐ（同じ既定値を二重に持たない）。 */
export function makeGoalDetail(overrides: Partial<GoalDetailRead> = {}): GoalDetailRead {
  return {
    ...makeGoal(),
    exam_subjects: [makeSubject()],
    materials: [],
    load_profiles: [],
    ...overrides,
  }
}
