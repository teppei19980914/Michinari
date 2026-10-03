import type { ProgressRegisterRequest } from '../../api/records'
import type { CategoryReportedState } from './categoryCompletion'
import { buildStudyLogPayload, type StudyLogFormValue } from './studyLogForm'
import { buildReadingLogPayload, type ReadingLogFormValue } from './readingLogForm'
import { buildWorkLogPayload, type WorkLogFormValue } from './workLogForm'

/** 進捗のみ登録で保持する下書き（実績のみ。日記・AI対話は持たない。仕様書6.6）。
 * useDailyReportDraftの戻り値がそのまま渡せる形にしている。 */
export type ProgressOnlyDraftValues = {
  studyLogValues: Record<number, StudyLogFormValue>
  readingLogValues: Record<number, ReadingLogFormValue>
  workLogValues: Record<number, WorkLogFormValue>
}

/** そのカテゴリに入力対象（教材・書籍・案件）があるか。
 * resolveVisibleReportTargetsの戻り値がそのまま渡せる形にしている。 */
export type ProgressOnlyTargetSections = {
  showExamSection: boolean
  showReadingSection: boolean
  showWorkSection: boolean
}

export type ProgressOnlyInput = {
  /** 資格試験の実績入力欄を表示するか。 */
  showExamSection: boolean
  /** 読書の想起入力欄を表示するか。 */
  showReadingSection: boolean
  /** 仕事の業務記録入力欄を表示するか。 */
  showWorkSection: boolean
  /** 登録時に送信する内容。表示していないカテゴリの実績は含めない。 */
  payload: ProgressRegisterRequest
  /** 登録ボタンを押せるか（送信対象が1件以上あるか）。 */
  canRegister: boolean
}

/**
 * SC-07 進捗のみ登録（仕様書6.6）で「どのカテゴリの入力欄を出すか」と「何を送信するか」を
 * まとめて決める純粋関数。
 *
 * 表示と送信を1つの関数で決めるのは、どちらも同じ規則（対象があり、かつ未確定のカテゴリのみ）
 * に従うためである。2箇所に分けて書くと、片方だけを直したときに「画面に出ていないカテゴリの
 * 実績を送る」状態が生まれる。これはサーバが確定済みカテゴリへの更新を拒否する
 * （record_service._ensure_category_not_reported → 14章 IMMUTABLE_RECORD）ため、
 * 確定済みカテゴリの実績を積んだまま送ると、未確定カテゴリの登録まで巻き添えで失敗する。
 * 下書きは既存の実績で初期化される（initStudyLogFormValues等）ので、確定済みカテゴリの
 * 入力欄を出さないだけでは送信対象から外れない点に注意する。
 *
 * 進捗のみ登録は日次報告（SC-06）と異なりカテゴリごとの確定を持たず、登録は1操作で
 * 全カテゴリ分をまとめて送る（サーバのregister_progressが3カテゴリを1リクエストで受け付ける）。
 *
 * @param source 入力対象の有無（resolveVisibleReportTargets）・カテゴリ別の確定状況・下書き
 * @returns 表示するセクションと送信内容
 * @example
 *   // 資格試験が確定済みで読書が未確定なら、読書だけを表示・送信する
 *   resolveProgressOnlyInput({ sections, reported: { isExamReported: true, ... }, draft })
 */
export function resolveProgressOnlyInput(source: {
  sections: ProgressOnlyTargetSections
  reported: CategoryReportedState
  draft: ProgressOnlyDraftValues
}): ProgressOnlyInput {
  const { sections, reported, draft } = source

  // 確定済みのカテゴリは変更できない（仕様書7.2）。対象があっても入力欄を出さない。
  const showExamSection = sections.showExamSection && !reported.isExamReported
  const showReadingSection = sections.showReadingSection && !reported.isReadingReported
  const showWorkSection = sections.showWorkSection && !reported.isWorkReported

  const studyLogs = showExamSection ? buildStudyLogPayload(draft.studyLogValues) : []
  const readingLogs = showReadingSection ? buildReadingLogPayload(draft.readingLogValues) : []
  const workLogs = showWorkSection ? buildWorkLogPayload(draft.workLogValues) : []

  return {
    showExamSection,
    showReadingSection,
    showWorkSection,
    payload: { study_logs: studyLogs, reading_logs: readingLogs, work_logs: workLogs },
    // サーバは3カテゴリのいずれも空の登録を拒否する（record_service.register_progress）。
    // 押してからエラーになるより、押せない状態で示すほうが操作が分かりやすい。
    canRegister: studyLogs.length + readingLogs.length + workLogs.length > 0,
  }
}
