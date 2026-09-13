import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { DailyRecordQueries } from './useDailyRecordQueries'
import { toCategoryReportedState } from './categoryCompletion'
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
 * 下書きは表示中のタブに関わらず全目標分を保持する。タブ切り替えは表示のみに作用し、確定は
 * カテゴリ単位で行うため、非表示のタブに入力済みの内容が確定時に失われることはない。
 *
 * @param queries 下書きの初期値の元になる取得結果
 * @param setSelectedGoalId 初期表示するタブを決めるための設定関数（useGoalReportTabs）
 */
export function useDailyReportDraft(
  queries: DailyRecordQueries,
  setSelectedGoalId: (goalId: number) => void,
): DailyReportDraft {
  const { record, quota, readingBooks, workAssignments, goals } = queries
  const [studyLogValues, setStudyLogValues] = useState<Record<number, StudyLogFormValue>>({})
  const [readingLogValues, setReadingLogValues] = useState<Record<number, ReadingLogFormValue>>({})
  const [workLogValues, setWorkLogValues] = useState<Record<number, WorkLogFormValue>>({})
  const [diaryValues, setDiaryValues] = useState<Record<number, DiaryFormValue>>({})
  const [chatMessages, setChatMessages] = useState<ChatMessageRead[]>([])
  // 初期化は取得完了後の1回だけ行う。再取得（確定後のinvalidate等）のたびに初期値へ戻すと、
  // 入力途中の下書きが消えてしまう。
  const hydratedRef = useRef(false)

  const recordData = record.data
  const quotaData = quota.data
  const readingBooksData = readingBooks.data
  const workAssignmentsData = workAssignments.data
  const goalsData = goals.data

  useEffect(() => {
    if (
      hydratedRef.current ||
      !recordData ||
      !quotaData ||
      !readingBooksData ||
      !workAssignmentsData ||
      !goalsData
    ) {
      return
    }
    hydratedRef.current = true
    setStudyLogValues(initStudyLogFormValues(quotaData, recordData.study_logs))
    setReadingLogValues(
      initReadingLogFormValues(
        readingBooksData.map((entry) => entry.book),
        recordData.reading_logs,
      ),
    )
    setWorkLogValues(
      initWorkLogFormValues(
        workAssignmentsData.map((entry) => entry.workAssignment),
        recordData.work_logs,
      ),
    )
    setDiaryValues(
      initDiaryFormValues(
        goalsData.filter((goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM'),
        recordData.diary_entries,
      ),
    )
    setChatMessages(recordData.chat_messages)
    const firstActiveGoal = goalsData.find((goal) => goal.status === 'ACTIVE')
    if (firstActiveGoal) {
      setSelectedGoalId(firstActiveGoal.id)
    }
  }, [recordData, quotaData, readingBooksData, workAssignmentsData, goalsData, setSelectedGoalId])

  // 確定済みカテゴリの下書きが残っていても、既にサーバへ反映済みのため警告対象にしない。
  const { isExamReported, isReadingReported, isWorkReported } = toCategoryReportedState(recordData)
  const hasUnsavedInput =
    (!isExamReported && (hasAnyStudyLogInput(studyLogValues) || hasAnyDiaryInput(diaryValues))) ||
    (!isReadingReported && hasAnyReadingLogInput(readingLogValues)) ||
    (!isWorkReported && hasAnyWorkLogInput(workLogValues))

  return {
    studyLogValues,
    setStudyLogValues,
    readingLogValues,
    setReadingLogValues,
    workLogValues,
    setWorkLogValues,
    diaryValues,
    setDiaryValues,
    chatMessages,
    setChatMessages,
    hasUnsavedInput,
  }
}
