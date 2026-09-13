import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { useToast } from '../components/Toast'
import { Button } from '../components/Button'
import { ROUTES } from '../constants/routes'
import { getQuota, getRecord, getToday, registerProgress } from '../api/records'
import { StudyLogFields } from '../features/record/StudyLogFields'
import { isFutureDate } from '../features/record/finalizableDate'
import { useSlotNames } from '../features/record/useSlotNames'
import { invalidateDailyRecordCaches } from '../features/record/invalidateDailyRecordCaches'
import { patchFormValue } from '../features/record/formValues'
import {
  buildStudyLogPayload,
  hasAnyStudyLogInput,
  initStudyLogFormValues,
  type StudyLogFormValue,
} from '../features/record/studyLogForm'

/** SC-07 進捗のみ登録（仕様書6.6）。実績入力領域のみを持ち、日記記述・AI対話領域は持たない。
 * 「確定前に画面を離脱した場合の警告」（仕様書6.5）はSC-06の完了条件としてのみ明記されており、
 * SC-07には記載がないため、本画面には離脱警告（useUnsavedChangesWarning/useBlocker）を
 * 設けていない。 */
export function ProgressOnlyPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const slotNames = useSlotNames()
  const { showApiError } = useToast()

  const recordQuery = useQuery({
    queryKey: ['record', targetDate],
    queryFn: () => getRecord(targetDate),
  })
  const quotaQuery = useQuery({
    queryKey: ['quota', targetDate],
    queryFn: () => getQuota(targetDate),
  })
  // 進捗のみ登録が可能なのは未来日以外（仕様書7.2「当日または前日以前」）。論理的な本日は
  // クライアントで算出せずサーバから取得する（技術選定書7.1「禁止事項」）。
  const todayQuery = useQuery({ queryKey: ['today'], queryFn: getToday })

  const [studyLogValues, setStudyLogValues] = useState<Record<number, StudyLogFormValue>>({})
  const hydratedRef = useRef(false)

  useEffect(() => {
    if (hydratedRef.current || !recordQuery.data || !quotaQuery.data) {
      return
    }
    hydratedRef.current = true
    setStudyLogValues(initStudyLogFormValues(quotaQuery.data, recordQuery.data.study_logs))
  }, [recordQuery.data, quotaQuery.data])

  const registerMutation = useMutation({
    mutationFn: () => registerProgress(targetDate, { study_logs: buildStudyLogPayload(studyLogValues) }),
    onSuccess: () => {
      invalidateDailyRecordCaches(queryClient, targetDate)
      navigate(ROUTES.dashboard)
    },
    onError: showApiError,
  })

  if (recordQuery.isLoading || quotaQuery.isLoading || todayQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (
    recordQuery.isError ||
    !recordQuery.data ||
    quotaQuery.isError ||
    !quotaQuery.data ||
    todayQuery.isError ||
    !todayQuery.data
  ) {
    return (
      <p className="p-6 text-sm text-red-600">
        {apiErrorMessage(recordQuery.error ?? quotaQuery.error ?? todayQuery.error)}
      </p>
    )
  }
  if (isFutureDate(targetDate, todayQuery.data.logical_date)) {
    // 未来日への実績登録はサーバが拒否する（仕様書7.2）。入力させてから送信時に弾くと入力内容が
    // 失われるため、その前に閲覧画面へ誘導する（日次報告画面の入力可能期間ガードと同じ方針）。
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }
  if (recordQuery.data.exam_record_state === 'REPORTED') {
    // このページはEXAM専用（study_logsのみ扱う）のため、資格勉強が確定済みなら
    // 変更不可（仕様書7.2）。閲覧画面へ誘導する。
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('progressOnly.title', { date: targetDate })}
      </h1>

      <StudyLogFields
        quotaItems={quotaQuery.data}
        values={studyLogValues}
        slotNames={slotNames}
        showMinutesOptionalNotice
        onChangeField={(materialId, field, value) =>
          setStudyLogValues((current) => patchFormValue(current, materialId, field, value))
        }
        onChangeSlotMinutes={(materialId, slotMinutes) =>
          setStudyLogValues((current) =>
            patchFormValue(current, materialId, 'slotMinutes', slotMinutes),
          )
        }
      />

      <div className="flex justify-end">
        <Button
          disabled={registerMutation.isPending || !hasAnyStudyLogInput(studyLogValues)}
          onClick={() => registerMutation.mutate()}
        >
          {t('progressOnly.registerButton')}
        </Button>
      </div>
    </div>
  )
}
