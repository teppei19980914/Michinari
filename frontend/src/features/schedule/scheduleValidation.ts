import type { components } from '../../types/api.d.ts'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

/**
 * スケジュール画面の入力中の検証（開発Todo_スケジュール・ガントチャート_v1.1 6.1・6.2）。
 * サーバー側（`schedule_service.validate_item_fields`）と同じルールのクライアント側ミラー。
 * 最終判定は常にサーバーで行う（6.1）。表示用の文言はロケールキー
 * （`schedule.validation.<code>`）で管理するため、ここではコード（識別子）のみを返す
 * （ゼロハードコーディング）。
 */
export type ScheduleFieldErrorCode =
  | 'TITLE_REQUIRED'
  | 'PLANNED_RANGE_INVALID'
  | 'ACTUAL_NOT_ALLOWED'
  | 'ACTUAL_START_REQUIRED'
  | 'ACTUAL_END_NOT_ALLOWED'
  | 'ACTUAL_END_REQUIRED'
  | 'ACTUAL_END_ONLY_NOT_ALLOWED'
  | 'ACTUAL_RANGE_INVALID'
  | 'ACTUAL_DATE_IN_FUTURE'

export type ScheduleItemFieldErrors = {
  title?: ScheduleFieldErrorCode
  plannedStartDate?: ScheduleFieldErrorCode
  plannedEndDate?: ScheduleFieldErrorCode
  actualStartDate?: ScheduleFieldErrorCode
  actualEndDate?: ScheduleFieldErrorCode
}

export type ScheduleItemFieldsInput = {
  title: string
  plannedStartDate: string
  plannedEndDate: string
  status: ScheduleItemStatus
  actualStartDate: string | null
  actualEndDate: string | null
}

/** 1行分の必須・日付整合・状況に応じた実績日の条件付き必須（6.2）をすべて検証する。 */
export function validateScheduleItemFields(
  input: ScheduleItemFieldsInput,
  today: string,
): ScheduleItemFieldErrors {
  const errors: ScheduleItemFieldErrors = {}

  if (!input.title.trim()) {
    errors.title = 'TITLE_REQUIRED'
  }

  if (input.plannedStartDate > input.plannedEndDate) {
    errors.plannedStartDate = 'PLANNED_RANGE_INVALID'
    errors.plannedEndDate = 'PLANNED_RANGE_INVALID'
  }

  if (input.status === 'NOT_STARTED') {
    if (input.actualStartDate !== null) errors.actualStartDate = 'ACTUAL_NOT_ALLOWED'
    if (input.actualEndDate !== null) errors.actualEndDate = 'ACTUAL_NOT_ALLOWED'
  } else if (input.status === 'IN_PROGRESS') {
    if (input.actualStartDate === null) errors.actualStartDate = 'ACTUAL_START_REQUIRED'
    if (input.actualEndDate !== null) errors.actualEndDate = 'ACTUAL_END_NOT_ALLOWED'
  } else if (input.status === 'DONE') {
    if (input.actualStartDate === null) errors.actualStartDate = 'ACTUAL_START_REQUIRED'
    if (input.actualEndDate === null) errors.actualEndDate = 'ACTUAL_END_REQUIRED'
  } else if (
    input.status === 'CANCELLED' &&
    input.actualStartDate === null &&
    input.actualEndDate !== null
  ) {
    errors.actualEndDate = 'ACTUAL_END_ONLY_NOT_ALLOWED'
  }

  if (
    input.actualStartDate !== null &&
    input.actualEndDate !== null &&
    input.actualStartDate > input.actualEndDate
  ) {
    errors.actualStartDate = 'ACTUAL_RANGE_INVALID'
    errors.actualEndDate = 'ACTUAL_RANGE_INVALID'
  }

  if (input.actualStartDate !== null && input.actualStartDate > today) {
    errors.actualStartDate = 'ACTUAL_DATE_IN_FUTURE'
  }
  if (input.actualEndDate !== null && input.actualEndDate > today) {
    errors.actualEndDate = 'ACTUAL_DATE_IN_FUTURE'
  }

  return errors
}

/** 1行分のエラーオブジェクトに、1件以上のエラーがあるかどうかを返す。 */
export function hasScheduleFieldErrors(errors: ScheduleItemFieldErrors): boolean {
  return Object.keys(errors).length > 0
}
