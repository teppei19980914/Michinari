import { differenceInCalendarDays, parseISO } from 'date-fns'

/**
 * 道のりマップ（開発Todo_道のりマップ_v1.0.md §0・§4）の座標計算。
 *
 * バックエンド（`GET /goals/{id}/roadmap`）が返す正規化された比率（0.0〜1.0）・日付から、
 * SVG描画用の0.0〜1.0座標（x=時間軸の位置、y=比率）へ変換する。SVGのviewBoxへの
 * 引き伸ばしは描画側（GoalRoadmapMini/GoalRoadmapTab）が行う（§0 U12「SVG座標への変換は
 * フロント側で行う」）。
 *
 * 資格（山）・読書（道）はいずれも「時間軸×比率」の2軸で表現し（計画線と実績線の
 * ズレで『まっすぐ向かう強み』を示す、要件2）、見た目の形（山か道か）は描画側の責務とする
 * （ganttGeometry.tsと同じ「純粋関数でレイアウト計算→テストで検証→コンポーネントで描画」
 * パターン）。仕事（足跡の積み上げ）は進捗量の概念が無いため（§0 U17）、
 * planned/actual は常に空配列になる。
 */

export type RoadmapPointInput = { date: string; ratio: number }
export type RoadmapFootprintInput = { date: string; has_input: boolean }

export type RoadmapLayoutInput = {
  start_date: string
  goal_date: string
  today_date: string
  progress_ratio: number
  planned_points: RoadmapPointInput[]
  actual_points: RoadmapPointInput[]
  footprint_dates: RoadmapFootprintInput[]
  replan_marks: RoadmapPointInput[]
  feedback_marks: string[]
  buffer_dates: string[]
}

export type LayoutPoint = { x: number; y: number }
export type LayoutMark = { x: number; y: number; date: string }
export type LayoutTick = { x: number; date: string }
export type LayoutFootprint = { x: number; y: number; date: string; hasInput: boolean }

export type RoadmapLayout = {
  /** 全体の時間軸の範囲（開始日〜終了日。ゴール超過時はtoday_dateまで延びる）。 */
  rangeStart: string
  rangeEnd: string
  plannedPath: LayoutPoint[]
  actualPath: LayoutPoint[]
  startPosition: LayoutPoint
  /** 現在地。仕事目標はyに意味が無いため描画側は使わない（§0 U17、xのみ使う）。 */
  currentPosition: LayoutPoint
  goalPosition: LayoutPoint
  replanMarks: LayoutMark[]
  feedbackMarks: LayoutTick[]
  bufferTicks: LayoutTick[]
  footprints: LayoutFootprint[]
}

function daysBetween(fromIso: string, toIso: string): number {
  return differenceInCalendarDays(parseISO(toIso), parseISO(fromIso))
}

function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value))
}

/** 日付を時間軸上の0.0〜1.0位置へ変換する。範囲が0日以下（境界ケース：開始日=終了日）の場合は
 * 全て起点（0）とする（ganttGeometry.tsの「範囲が0日の場合」と同じ考え方）。 */
function timeFraction(dateIso: string, rangeStart: string, rangeEnd: string): number {
  const totalDays = daysBetween(rangeStart, rangeEnd)
  if (totalDays <= 0) {
    return 0
  }
  return clampUnit(daysBetween(rangeStart, dateIso) / totalDays)
}

function toPath(
  points: RoadmapPointInput[],
  rangeStart: string,
  rangeEnd: string,
): LayoutPoint[] {
  return points.map((p) => ({ x: timeFraction(p.date, rangeStart, rangeEnd), y: clampUnit(p.ratio) }))
}

function toMarks(
  points: RoadmapPointInput[],
  rangeStart: string,
  rangeEnd: string,
): LayoutMark[] {
  return points.map((p) => ({
    x: timeFraction(p.date, rangeStart, rangeEnd),
    y: clampUnit(p.ratio),
    date: p.date,
  }))
}

function toTicks(dates: string[], rangeStart: string, rangeEnd: string): LayoutTick[] {
  return dates.map((date) => ({ x: timeFraction(date, rangeStart, rangeEnd), date }))
}

/** 足跡だけの日（読書：ページ未入力）は、直前の実績点の比率を引き継いで道の上に置く
 * （バックエンドのfootprint_datesは比率を持たないため、§3.1 S-02。actual_pointsは日付昇順
 * である前提、roadmap_service._reading_roadmapの実装に合わせる）。実績点が1件も無い場合は
 * 0.0とする（境界ケース：記録0件）。 */
function stepRatioAt(actualPoints: RoadmapPointInput[], dateIso: string): number {
  let current = 0
  for (const point of actualPoints) {
    if (point.date > dateIso) {
      break
    }
    current = point.ratio
  }
  return clampUnit(current)
}

function toFootprints(
  footprints: RoadmapFootprintInput[],
  actualPoints: RoadmapPointInput[],
  rangeStart: string,
  rangeEnd: string,
): LayoutFootprint[] {
  return footprints.map((f) => ({
    x: timeFraction(f.date, rangeStart, rangeEnd),
    y: stepRatioAt(actualPoints, f.date),
    date: f.date,
    hasInput: f.has_input,
  }))
}

/** 道のりマップのレイアウトを算出する（§4 処理フロー）。 */
export function computeRoadmapLayout(roadmap: RoadmapLayoutInput): RoadmapLayout {
  const rangeStart = roadmap.start_date
  // ゴールを過ぎた日（境界ケース：ゴール超過）も実績を描き続けられるよう、範囲を
  // today_dateまで延ばす（roadmap_serviceのoverall_toと同じ考え方）。
  const rangeEnd = roadmap.today_date > roadmap.goal_date ? roadmap.today_date : roadmap.goal_date

  const actualPath = toPath(roadmap.actual_points, rangeStart, rangeEnd)
  const currentY =
    actualPath.length > 0 ? actualPath[actualPath.length - 1].y : clampUnit(roadmap.progress_ratio)

  return {
    rangeStart,
    rangeEnd,
    plannedPath: toPath(roadmap.planned_points, rangeStart, rangeEnd),
    actualPath,
    startPosition: { x: 0, y: 0 },
    currentPosition: { x: timeFraction(roadmap.today_date, rangeStart, rangeEnd), y: currentY },
    goalPosition: { x: timeFraction(roadmap.goal_date, rangeStart, rangeEnd), y: 1 },
    replanMarks: toMarks(roadmap.replan_marks, rangeStart, rangeEnd),
    feedbackMarks: toTicks(roadmap.feedback_marks, rangeStart, rangeEnd),
    bufferTicks: toTicks(roadmap.buffer_dates, rangeStart, rangeEnd),
    footprints: toFootprints(roadmap.footprint_dates, roadmap.actual_points, rangeStart, rangeEnd),
  }
}
