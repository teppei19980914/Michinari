import type { Granularity } from '../api/analytics'

/** 仕事目標の定期報告の種別（月次／半期）。クエリキーの一部になるためここに置く。 */
export type WorkReportKind = 'monthly' | 'semiannual'

/**
 * TanStack Query のキャッシュキー（CODING_RULES.md 置き場所ルール「コード上の名前」）。
 *
 * 取得（useQuery）と無効化（invalidateQueries）は必ず同じキーを指す必要があり、文字列を
 * 各画面へ直接書くと、片方だけ書き換えて「更新したのに古い値が残る」不具合になる。実際に
 * 96箇所へ散在していたため1箇所へ集約する。
 *
 * **前方一致に依存している組み合わせ**（キーを変えるときはセットで確認する）。
 * TanStack Query の `invalidateQueries` は指定したキーで始まるクエリをすべて無効化する。
 * - `calendar()` の無効化で `calendarRange()` も無効化される
 * - `retrospective()` の無効化で `retrospectiveView()` も無効化される
 * - `workReport()` の無効化で `workReportPeriod()` も無効化される
 * この関係を壊さないため、長いキーは必ず短いキーと同じ要素から始める。
 */
export const QUERY_KEYS = {
  // --- 目標 ---
  goals: () => ['goals'] as const,
  /** goalIdがnullを取りうるのは、目標が未選択の間だけ`enabled: false`で待機する
   * 呼び出し（CalendarPageの目標詳細）があるため。選択後は同じキーで取得に切り替わる。 */
  goal: (goalId: number | null) => ['goal', goalId] as const,
  goalSlotAllocations: (goalId: number) => ['goal-slot-allocations', goalId] as const,
  materialSlotCheck: (materialId: number) => ['material-slot-check', materialId] as const,

  // --- 日次記録 ---
  record: (targetDate: string) => ['record', targetDate] as const,
  quota: (targetDate: string) => ['quota', targetDate] as const,
  today: () => ['today'] as const,
  dashboard: () => ['dashboard'] as const,
  dailyMessage: () => ['daily-message'] as const,
  activeReadingBooks: () => ['activeReadingBooks'] as const,
  activeWorkAssignments: () => ['activeWorkAssignments'] as const,

  // --- カレンダー（calendar が calendarRange の前方一致になる） ---
  calendar: () => ['calendar'] as const,
  calendarRange: (dateFrom: string, dateTo: string) => ['calendar', dateFrom, dateTo] as const,

  // --- 分析 ---
  analyticsBaselines: (goalId: number) => ['analytics', 'baselines', goalId] as const,
  analyticsForecast: (goalId: number) => ['analytics', 'forecast', goalId] as const,
  analyticsGantt: (goalId: number) => ['analytics', 'gantt', goalId] as const,
  analyticsGrowthDescriptions: (goalId: number) =>
    ['analytics', 'growth-descriptions', goalId] as const,
  analyticsProgress: (goalId: number) => ['analytics', 'progress', goalId] as const,
  analyticsQuality: (goalId: number, granularity: Granularity) =>
    ['analytics', 'quality', goalId, granularity] as const,
  analyticsReadingLogs: (goalId: number) => ['analytics', 'reading-logs', goalId] as const,
  analyticsSpeed: (goalId: number) => ['analytics', 'speed', goalId] as const,
  analyticsWorkLogs: (goalId: number) => ['analytics', 'work-logs', goalId] as const,

  // --- 振り返り（retrospective が retrospectiveView の前方一致になる） ---
  retrospective: (goalId: number) => ['retrospective', goalId] as const,
  retrospectiveView: (goalId: number, anonymize: boolean) =>
    ['retrospective', goalId, anonymize] as const,
  knowledgeExportProgress: (goalId: number) => ['knowledgeExportProgress', goalId] as const,

  // --- 仕事目標の定期報告（workReport が workReportPeriod の前方一致になる） ---
  workReport: (kind: WorkReportKind, goalId: number) => ['workReport', kind, goalId] as const,
  workReportPeriod: (kind: WorkReportKind, goalId: number, period: string) =>
    ['workReport', kind, goalId, period] as const,

  // --- リソース設定 ---
  resourceSlots: () => ['resource-slots'] as const,
  resourceAllocation: () => ['resource-allocation'] as const,
  dayTypeDefaults: () => ['day-type-defaults'] as const,
  dayBoundaryHour: () => ['day-boundary-hour'] as const,
  holidayTreatAsBuffer: () => ['holiday-treat-as-buffer'] as const,

  // --- 設定・システム ---
  settings: () => ['settings'] as const,
  systemInfo: () => ['systemInfo'] as const,
  backups: () => ['backups'] as const,
  aiStatus: () => ['ai-status'] as const,
  aiAssistants: () => ['ai-assistants'] as const,
  promptTemplates: () => ['prompt-templates'] as const,
} as const
