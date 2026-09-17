import { useEffect, type Dispatch, type SetStateAction } from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { DailyRecordQueries } from './useDailyRecordQueries'
import { toCategoryReportedState } from './categoryCompletion'
import { applySetStateAction, useDraftStore } from './dailyReportDraftStore'
import {
  hasAnyStudyLogInput,
  initStudyLogFormValues,
  type StudyLogFormValue,
} from './studyLogForm'
import {
  hasAnyReadingLogInput,
  initReadingLogFormValues,
  type ReadingLogFormValue,
} from './readingLogForm'
import { hasAnyWorkLogInput, initWorkLogFormValues, type WorkLogFormValue } from './workLogForm'
import { hasAnyDiaryInput, initDiaryFormValues, type DiaryFormValue } from './diaryForm'

export type DailyReportDraft = {
  studyLogValues: Record<number, StudyLogFormValue>
  setStudyLogValues: Dispatch<SetStateAction<Record<number, StudyLogFormValue>>>
  readingLogValues: Record<number, ReadingLogFormValue>
  setReadingLogValues: Dispatch<SetStateAction<Record<number, ReadingLogFormValue>>>
  workLogValues: Record<number, WorkLogFormValue>
  setWorkLogValues: Dispatch<SetStateAction<Record<number, WorkLogFormValue>>>
  diaryValues: Record<number, DiaryFormValue>
  setDiaryValues: Dispatch<SetStateAction<Record<number, DiaryFormValue>>>
  chatMessages: ChatMessageRead[]
  setChatMessages: Dispatch<SetStateAction<ChatMessageRead[]>>
  /** 未確定カテゴリに入力が残っているか（離脱警告の判定に使う）。 */
  hasUnsavedInput: boolean
}

/**
 * SC-06 日次報告の下書き（実績入力・日記・AI対話履歴）を保持する。
 *
 * 実績・日記は確定（finalize）まで一切サーバへ保存しない下書き値であり、AI対話もこの下書きを
 * プロンプトへ渡すのみで永続化しない（仕様書16.7「AI呼び出しが失敗しても実績入力が失われない」）
 * ため、ローカルstateを常に正とする。
 *
 * 実体は`dailyReportDraftStore`（App.tsxのLayoutに置いたDailyReportDraftProvider）が
 * `storeKey`ごとに保持する（記録画面改善タスク2026-09-17）。ページコンポーネントの
 * useStateではなく上位のProviderに置くことで、確定前に別画面へ移動して戻っても下書きが
 * 復元される（要件E）。「取得完了後の初期化を1回だけ行う」という制約
 * （再取得のたびに初期値へ戻すと入力途中の下書きが消える）は、hydratedフラグを
 * storeKey単位で保持することで維持している。
 *
 * 下書きは表示中のタブに関わらず全目標分を保持する。タブ切り替えは表示のみに作用し、確定は
 * カテゴリ単位で行うため、非表示のタブに入力済みの内容が確定時に失われることはない。
 *
 * 進捗のみ登録（SC-07）も実績の下書きを同じ規則で保持するためこのフックを共有する
 * （CODING_RULES.md「①DRYの原則」）。SC-07は日記・AI対話・目標タブを持たないため（仕様書6.6）、
 * 日記・対話履歴の初期化結果を参照しない。SC-06とSC-07は同じ日付でも別々の下書きを持つよう、
 * 呼び出し側が画面種別を含めた`storeKey`を渡す（例: `daily-report:2026-09-17` /
 * `progress-only:2026-09-17`）。
 *
 * 初期表示タブ（目標タブの選択状態）は本フックの関心事ではなくuseGoalReportTabsが自身で
 * 持つ（記録画面改善タスク2026-09-17）。以前は本フックの初期化と結合していたが、下書きの
 * hydrateがstoreKey単位で1回だけになったことで、画面の再訪問時にタブ選択だけ再初期化されない
 * 問題が起きたため分離した。
 *
 * @param storeKey 下書きを一意に識別するキー（画面種別+対象日）
 * @param queries 下書きの初期値の元になる取得結果
 */
export function useDailyReportDraft(
  storeKey: string,
  queries: DailyRecordQueries,
): DailyReportDraft {
  const { record, quota, readingBooks, workAssignments, goals } = queries
  const store = useDraftStore()
  const draftState = store.getDraft(storeKey)

  const recordData = record.data
  const quotaData = quota.data
  const readingBooksData = readingBooks.data
  const workAssignmentsData = workAssignments.data
  const goalsData = goals.data

  useEffect(() => {
    if (
      draftState.hydrated ||
      !recordData ||
      !quotaData ||
      !readingBooksData ||
      !workAssignmentsData ||
      !goalsData
    ) {
      return
    }
    store.setDraft(storeKey, (current) => ({
      ...current,
      hydrated: true,
      studyLogValues: initStudyLogFormValues(quotaData, recordData.study_logs),
      readingLogValues: initReadingLogFormValues(
        readingBooksData.map((entry) => entry.book),
        recordData.reading_logs,
      ),
      workLogValues: initWorkLogFormValues(
        workAssignmentsData.map((entry) => entry.workAssignment),
        recordData.work_logs,
      ),
      diaryValues: initDiaryFormValues(
        goalsData.filter((goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM'),
        recordData.diary_entries,
      ),
      chatMessages: recordData.chat_messages,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    draftState.hydrated,
    recordData,
    quotaData,
    readingBooksData,
    workAssignmentsData,
    goalsData,
    storeKey,
  ])

  // 確定済みカテゴリの下書きが残っていても、既にサーバへ反映済みのため警告対象にしない。
  const { isExamReported, isReadingReported, isWorkReported } = toCategoryReportedState(recordData)
  const hasUnsavedInput =
    (!isExamReported &&
      (hasAnyStudyLogInput(draftState.studyLogValues) || hasAnyDiaryInput(draftState.diaryValues))) ||
    (!isReadingReported && hasAnyReadingLogInput(draftState.readingLogValues)) ||
    (!isWorkReported && hasAnyWorkLogInput(draftState.workLogValues))

  const setStudyLogValues: Dispatch<SetStateAction<Record<number, StudyLogFormValue>>> = (action) =>
    store.setDraft(storeKey, (current) => ({
      ...current,
      studyLogValues: applySetStateAction(action, current.studyLogValues),
    }))
  const setReadingLogValues: Dispatch<SetStateAction<Record<number, ReadingLogFormValue>>> = (
    action,
  ) =>
    store.setDraft(storeKey, (current) => ({
      ...current,
      readingLogValues: applySetStateAction(action, current.readingLogValues),
    }))
  const setWorkLogValues: Dispatch<SetStateAction<Record<number, WorkLogFormValue>>> = (action) =>
    store.setDraft(storeKey, (current) => ({
      ...current,
      workLogValues: applySetStateAction(action, current.workLogValues),
    }))
  const setDiaryValues: Dispatch<SetStateAction<Record<number, DiaryFormValue>>> = (action) =>
    store.setDraft(storeKey, (current) => ({
      ...current,
      diaryValues: applySetStateAction(action, current.diaryValues),
    }))
  const setChatMessages: Dispatch<SetStateAction<ChatMessageRead[]>> = (action) =>
    store.setDraft(storeKey, (current) => ({
      ...current,
      chatMessages: applySetStateAction(action, current.chatMessages),
    }))

  return {
    studyLogValues: draftState.studyLogValues,
    setStudyLogValues,
    readingLogValues: draftState.readingLogValues,
    setReadingLogValues,
    workLogValues: draftState.workLogValues,
    setWorkLogValues,
    diaryValues: draftState.diaryValues,
    setDiaryValues,
    chatMessages: draftState.chatMessages,
    setChatMessages,
    hasUnsavedInput,
  }
}
