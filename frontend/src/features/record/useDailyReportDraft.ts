import { useEffect, type Dispatch, type SetStateAction } from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { DailyRecordQueries } from './useDailyRecordQueries'
import { toCategoryReportedState } from './categoryCompletion'
import {
  applySetStateAction,
  useDraftStore,
  type CategoryDraftState,
} from './dailyReportDraftStore'
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

type IncomingDraftValues = {
  studyLogValues: Record<number, StudyLogFormValue>
  readingLogValues: Record<number, ReadingLogFormValue>
  workLogValues: Record<number, WorkLogFormValue>
  diaryValues: Record<number, DiaryFormValue>
}

/** 取得結果から4カテゴリ分の初期値を組み立てる。hydrate（初回）とマージ（hydrate後の
 * 差分反映）の両方が同じ組み立て方を必要とするため、ここへ集約する
 * （CODING_RULES.md「①DRYの原則」）。 */
function computeIncomingDraftValues(queries: DailyRecordQueries): IncomingDraftValues | null {
  const recordData = queries.record.data
  const quotaData = queries.quota.data
  const readingBooksData = queries.readingBooks.data
  const workAssignmentsData = queries.workAssignments.data
  const goalsData = queries.goals.data
  if (!recordData || !quotaData || !readingBooksData || !workAssignmentsData || !goalsData) {
    return null
  }
  return {
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
  }
}

/** `incoming`にしか無いidだけを`current`へ補う。既にある値（入力途中の下書き）は
 * 上書きしない。変化が無ければ同一参照を返し、呼び出し側で無駄な`setDraft`を避けられる
 * ようにする。 */
function mergeNewEntries<T>(
  current: Record<number, T>,
  incoming: Record<number, T>,
): Record<number, T> {
  const missingIds = Object.keys(incoming).filter((id) => !(id in current))
  if (missingIds.length === 0) {
    return current
  }
  const merged = { ...current }
  for (const id of missingIds) {
    merged[Number(id)] = incoming[Number(id)]
  }
  return merged
}

/** 下書きをstoreKeyごとに1回だけ取得結果で初期化する（hydrate）。1関数100行の上限
 * （CODING_RULES.md「保守性（複雑度）」）のため`useDailyReportDraft`本体から切り出した。 */
function useHydrateDraftOnce(
  store: ReturnType<typeof useDraftStore>,
  storeKey: string,
  hydrated: boolean,
  queries: DailyRecordQueries,
): void {
  const recordData = queries.record.data
  const quotaData = queries.quota.data
  const readingBooksData = queries.readingBooks.data
  const workAssignmentsData = queries.workAssignments.data
  const goalsData = queries.goals.data

  useEffect(() => {
    if (hydrated || !recordData) {
      return
    }
    const incoming = computeIncomingDraftValues(queries)
    if (!incoming) {
      return
    }
    store.setDraft(storeKey, (current) => ({
      ...current,
      hydrated: true,
      ...incoming,
      chatMessages: recordData.chat_messages,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, recordData, quotaData, readingBooksData, workAssignmentsData, goalsData, storeKey])
}

/** hydrate後に新規作成された教材・書籍・案件・目標のidを下書きへ補う
 * （`useDailyReportDraft`本体のJSDoc参照）。既存の下書き値（入力途中のもの含む）は
 * 一切上書きしない。事前にmergeNewEntriesの結果が現在の下書きと変わらないかを確認し、
 * 変化が無ければsetDraft自体を呼ばない（再取得のたびにProvider配下を無駄に再描画しない
 * ため）。1関数100行の上限のため`useDailyReportDraft`本体から切り出した。 */
function useMergeNewlyCreatedEntries(
  store: ReturnType<typeof useDraftStore>,
  storeKey: string,
  draftState: CategoryDraftState,
  queries: DailyRecordQueries,
): void {
  const recordData = queries.record.data
  const quotaData = queries.quota.data
  const readingBooksData = queries.readingBooks.data
  const workAssignmentsData = queries.workAssignments.data
  const goalsData = queries.goals.data

  useEffect(() => {
    if (!draftState.hydrated) {
      return
    }
    const incoming = computeIncomingDraftValues(queries)
    if (!incoming) {
      return
    }
    // 事前にdraftState基準でmergeNewEntriesを試算し、4カテゴリとも変化が無ければ
    // setDraft自体を呼ばずに抜ける（再取得のたびにProvider配下を無駄に再描画しない
    // ため）。変化がある場合の実際の更新は、setDraftの関数形（current引数）を使って
    // 改めて計算し直す。ここでの`draftState`はレンダー時点のスナップショットであり、
    // Reactの状態更新は非同期にバッチされ得るため、実際に適用する値は
    // setDraftが渡す最新の`current`を基準に算出するのが安全なため（試算用と
    // 適用用で2回計算しているのは意図的）。
    const studyLogValues = mergeNewEntries(draftState.studyLogValues, incoming.studyLogValues)
    const readingLogValues = mergeNewEntries(draftState.readingLogValues, incoming.readingLogValues)
    const workLogValues = mergeNewEntries(draftState.workLogValues, incoming.workLogValues)
    const diaryValues = mergeNewEntries(draftState.diaryValues, incoming.diaryValues)
    if (
      studyLogValues === draftState.studyLogValues &&
      readingLogValues === draftState.readingLogValues &&
      workLogValues === draftState.workLogValues &&
      diaryValues === draftState.diaryValues
    ) {
      return
    }
    store.setDraft(storeKey, (current) => ({
      ...current,
      studyLogValues: mergeNewEntries(current.studyLogValues, incoming.studyLogValues),
      readingLogValues: mergeNewEntries(current.readingLogValues, incoming.readingLogValues),
      workLogValues: mergeNewEntries(current.workLogValues, incoming.workLogValues),
      diaryValues: mergeNewEntries(current.diaryValues, incoming.diaryValues),
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
}

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
 * hydrate後に新規作成された教材・書籍・案件・目標は、別途マージで補う（後述）。
 * `DailyReportDraftProvider`はApp.tsxのLayoutに置かれ全画面で1つを共有するため、SC-06/SC-07を
 * 開いたままアプリ内遷移で目標詳細画面（教材・書籍・案件の追加）やウィザード（資格試験目標の
 * 新規作成）へ行って戻ってくると、hydrateはstoreKey単位で1回きりのまま、対応する
 * `readingBooks`等のクエリだけが最新化される。この食い違いを放置すると、新しく増えた
 * id分の下書き値が一度も作られず、実績入力欄が`if (!value) return null`で空のまま
 * 表示され、そのまま確定（実績が空で報告済みになる）できてしまう不具合があった
 * （2026-09-18、日次報告画面を開いた後に読書目標を新規作成したケースで発覚。データ構造上は
 * 入力欄はあるべきだが値が存在しないため描画されず、利用者には入力手段が無い画面に見えた）。
 *
 * @param storeKey 下書きを一意に識別するキー（画面種別+対象日）
 * @param queries 下書きの初期値の元になる取得結果
 */
export function useDailyReportDraft(
  storeKey: string,
  queries: DailyRecordQueries,
): DailyReportDraft {
  const store = useDraftStore()
  const draftState = store.getDraft(storeKey)
  const recordData = queries.record.data

  useHydrateDraftOnce(store, storeKey, draftState.hydrated, queries)
  useMergeNewlyCreatedEntries(store, storeKey, draftState, queries)

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
