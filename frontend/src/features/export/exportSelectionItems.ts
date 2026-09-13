/** ナレッジエクスポート（SC-13）の出力項目の一覧と既定値。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値だけをこのファイルへ分ける。
 *
 * 教材構成・品質指標推移・リプラン履歴・週次要約・日記本文・AI対話履歴・受験結果は、
 * 読書目標・仕事目標には該当データが無いため選択肢自体を表示しない（仕様書6.10「読書目標の
 * 場合」「仕事目標の場合」、設計書データ構造編7.1）。summary・daily_records・retrospectiveは
 * 読書・仕事それぞれの読み替えラベルを持つ。 */
import type { ExportSelection } from '../../api/export'

export interface ExportSelectionItem {
  field: keyof ExportSelection
  labelKey: string
  readingLabelKey?: string
  workLabelKey?: string
  hiddenForReadingOrWork?: boolean
}

export const SELECTION_ITEMS: ExportSelectionItem[] = [
  { field: 'goal_overview', labelKey: 'knowledgeExport.selection.goalOverview' },
  {
    field: 'materials',
    labelKey: 'knowledgeExport.selection.materials',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'summary',
    labelKey: 'knowledgeExport.selection.summary',
    readingLabelKey: 'knowledgeExport.selection.readingSummary',
    workLabelKey: 'knowledgeExport.selection.workSummary',
  },
  {
    field: 'daily_records',
    labelKey: 'knowledgeExport.selection.dailyRecords',
    readingLabelKey: 'knowledgeExport.selection.readingDailyRecords',
    workLabelKey: 'knowledgeExport.selection.workDailyRecords',
  },
  {
    field: 'quality_trend',
    labelKey: 'knowledgeExport.selection.qualityTrend',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'replan_history',
    labelKey: 'knowledgeExport.selection.replanHistory',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'weekly_summaries',
    labelKey: 'knowledgeExport.selection.weeklySummaries',
    hiddenForReadingOrWork: true,
  },
  { field: 'diary', labelKey: 'knowledgeExport.selection.diary', hiddenForReadingOrWork: true },
  {
    field: 'ai_dialogue',
    labelKey: 'knowledgeExport.selection.aiDialogue',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'exam_results',
    labelKey: 'knowledgeExport.selection.examResults',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'retrospective',
    labelKey: 'knowledgeExport.selection.retrospective',
    readingLabelKey: 'knowledgeExport.selection.readingRetrospective',
    workLabelKey: 'knowledgeExport.selection.workRetrospective',
  },
]

/** 出力項目の既定値。日記本文とAI対話履歴は本文をそのまま含めるため既定でオフにする。 */
export const DEFAULT_SELECTION: ExportSelection = {
  goal_overview: true,
  materials: true,
  summary: true,
  daily_records: true,
  quality_trend: true,
  replan_history: true,
  weekly_summaries: true,
  diary: false,
  ai_dialogue: false,
  exam_results: true,
  retrospective: true,
}
