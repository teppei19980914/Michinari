/** 描画テスト用のAPIレスポンス組み立て（Phase 34）。
 *
 * `GoalDetailRead` などの自動生成型は必須項目が多く、各テストで丸ごと書くと
 * 「そのテストが何を意図しているか」がフィクスチャの中に埋もれる。既定値を1箇所へ置き、
 * 各テストは検証したい項目だけを上書きする（CODING_RULES.md ①DRYの原則）。
 *
 * 値は「型を満たす無難な既定値」であり、特定の仕様を表すものではない。仕様上の意味を
 * 持たせたい値は、必ず呼び出し側で明示的に上書きすること。 */
import type {
  GoalDetailRead,
  MaterialRead,
  SubjectRead,
} from '../api/goals'

/** 既定の目標ID。個別の値に意味はないが、取り違えを見つけやすいよう各IDはずらしてある。 */
export const GOAL_ID = 1
export const SUBJECT_ID = 11
export const MATERIAL_ID = 21

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

export function makeGoalDetail(overrides: Partial<GoalDetailRead> = {}): GoalDetailRead {
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
    exam_subjects: [makeSubject()],
    materials: [],
    load_profiles: [],
    ...overrides,
  }
}
