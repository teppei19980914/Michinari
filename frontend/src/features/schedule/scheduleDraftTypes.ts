import type { ScheduleItemStatus, ScheduleRead, ScheduleSaveRequest } from '../../api/schedule'

/**
 * スケジュールタブのローカル編集状態（ドラフト）の型と、サーバー表現との変換
 * （開発Todo_スケジュール・ガントチャート_v1.1 D-05〜D-08・D-12）。`useScheduleEditorState`
 * から純粋関数部分を分離し、直接テストできるようにする（CODING_RULES.md「保守性」）。
 */

export type ScheduleDraftColumn = {
  key: string
  id: number | null
  tempKey: string | null
  name: string
}

export type ScheduleDraftItem = {
  key: string
  id: number | null
  tempKey: string | null
  title: string
  description: string | null
  plannedStartDate: string
  plannedEndDate: string
  status: ScheduleItemStatus
  actualStartDate: string | null
  actualEndDate: string | null
  cells: Record<string, string>
}

export type ScheduleDraft = {
  revision: number
  columns: ScheduleDraftColumn[]
  items: ScheduleDraftItem[]
}

/** `ScheduleDraftItem`のうち、1セルとして編集できる既定7列のフィールド名（D-08）。
 * 複数ファイルで同じ分岐を扱うため、この1箇所にまとめる（DRYの原則）。 */
export type ScheduleDraftFieldKey =
  | 'title'
  | 'description'
  | 'plannedStartDate'
  | 'plannedEndDate'
  | 'actualStartDate'
  | 'actualEndDate'

/** 既存はid、新規はtemp_keyで対応付ける（本書8.1）。行・列・セルの参照キーを統一する。 */
export function columnKey(id: number | null, tempKey: string | null): string {
  return id !== null ? `id:${id}` : `temp:${tempKey}`
}

/** サーバー応答（`GET .../schedule`）をドラフト形式へ変換する（セルはcolumn_idキーのマップにする）。 */
export function toDraft(data: ScheduleRead): ScheduleDraft {
  const columns: ScheduleDraftColumn[] = data.columns.map((column) => ({
    key: columnKey(column.id, null),
    id: column.id,
    tempKey: null,
    name: column.name,
  }))
  const items: ScheduleDraftItem[] = data.items.map((item) => ({
    key: columnKey(item.id, null),
    id: item.id,
    tempKey: null,
    title: item.title,
    description: item.description,
    plannedStartDate: item.planned_start_date,
    plannedEndDate: item.planned_end_date,
    status: item.status,
    actualStartDate: item.actual_start_date,
    actualEndDate: item.actual_end_date,
    cells: Object.fromEntries(
      item.cells.map((cell) => [columnKey(cell.column_id, null), cell.value]),
    ),
  }))
  return { revision: data.revision, columns, items }
}

/** ドラフトを一括保存APIのリクエスト形式へ変換する（既存の行・列はid、新規はtemp_keyで指定）。 */
export function buildSaveRequest(draft: ScheduleDraft): ScheduleSaveRequest {
  return {
    revision: draft.revision,
    columns: draft.columns.map((column) =>
      column.id !== null
        ? { id: column.id, name: column.name }
        : { temp_key: column.tempKey as string, name: column.name },
    ),
    items: draft.items.map((item) => ({
      id: item.id ?? undefined,
      title: item.title,
      description: item.description,
      planned_start_date: item.plannedStartDate,
      planned_end_date: item.plannedEndDate,
      status: item.status,
      actual_start_date: item.actualStartDate,
      actual_end_date: item.actualEndDate,
      cells: draft.columns.map((column) =>
        column.id !== null
          ? { column_id: column.id, value: item.cells[column.key] ?? '' }
          : { column_temp_key: column.tempKey as string, value: item.cells[column.key] ?? '' },
      ),
    })),
  }
}

/** `columns`・`items`のみを比較する（未保存判定用。固定の行数・列数は別API・別状態のため
 * 対象外、本書7.1「固定の設定の変更ではrevisionを増やさない」）。 */
export function draftContentEquals(a: ScheduleDraft, b: ScheduleDraft): boolean {
  return (
    JSON.stringify({ columns: a.columns, items: a.items }) ===
    JSON.stringify({ columns: b.columns, items: b.items })
  )
}
