import type { ReactNode, Ref } from 'react'
import { t, rangeSeparator } from '../../locales/t'
import type { GoalCategory } from '../../api/goals'
import type { SummaryCardRead } from '../../api/summaryCard'
import { GoalRoadmapMini } from '../goal/GoalRoadmapMini'
import { buildSummaryCardTextLines, type SummaryCardTextLine } from './summaryCardLayout'
import type { SummaryCardVisibility } from './summaryCardVisibility'

export type SummaryCardPreviewProps = {
  ref?: Ref<SVGSVGElement>
  goalName: string
  category: GoalCategory
  period: { dateFrom: string; dateTo: string }
  aggregate: SummaryCardRead
  visibility: SummaryCardVisibility
  sentence: string | null
}

const WIDTH = 600
const PADDING = 32
const HEADER_HEIGHT = 64
const LINE_HEIGHT = 24
const ROADMAP_HEIGHT = 56

/** テキスト行1件が占める縦幅（見出し＋値、節目は値が複数件になるため加算する）。モジュール
 * 定数`LINE_HEIGHT`（1行分の行高）とは明確に区別する名前にする（スタイルレビュー指摘、
 * 2026-11-13。大文字/小文字の違いだけの名前は呼び出し元を読むときに混同しやすい）。 */
function lineBlockHeight(line: SummaryCardTextLine): number {
  const valueCount = line.key === 'milestones' ? Math.max(1, line.values.length) : 1
  return LINE_HEIGHT * (1 + valueCount)
}

/** 各行の見出しを描くY座標を先に積み上げておく（JSX構築中にループ変数を書き換えると
 * oxlint react(immutability)に抵触するため、レンダー前に関数的に計算する）。 */
function labelPositions(lines: SummaryCardTextLine[], startY: number): number[] {
  const positions: number[] = []
  lines.reduce((y, line) => {
    positions.push(y)
    return y + lineBlockHeight(line)
  }, startY)
  return positions
}

function renderLineValues(line: SummaryCardTextLine, x: number, y: number): ReactNode {
  if (line.key === 'milestones') {
    return line.values.map((value, index) => (
      <text key={value} x={x} y={y + LINE_HEIGHT * (index + 1)} fontSize={14}>
        {value}
      </text>
    ))
  }
  return (
    <text x={x} y={y + LINE_HEIGHT} fontSize={14}>
      {line.value}
    </text>
  )
}

/** ふりかえりまとめ・共有カードのSVG本体（仕様書6.2 SC-03・6.10 SC-13、ロジック・プロンプト編
 * 28.2「画像化（フロント）」）。ここで描く内容がそのままPNG化・コピー対象になるため、外部
 * スタイルシート（Tailwind）に依存する要素は置かない（色・寸法は全てSVG属性として直接渡す。
 * `summaryCardImage.ts`がXMLSerializerで文字列化する際にTailwindクラスは引き継がれない）。 */
export function SummaryCardPreview({
  ref,
  goalName,
  category,
  period,
  aggregate,
  visibility,
  sentence,
}: SummaryCardPreviewProps) {
  const textLines = buildSummaryCardTextLines({ aggregate, visibility, sentence })
  const roadmapVisible = visibility.roadmap
  const bodyHeight = textLines.reduce((sum, line) => sum + lineBlockHeight(line), 0)
  const height =
    PADDING * 2 + HEADER_HEIGHT + bodyHeight + (roadmapVisible ? ROADMAP_HEIGHT : 0)

  const labelYs = labelPositions(textLines, PADDING + HEADER_HEIGHT)

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${WIDTH} ${height}`}
      width={WIDTH}
      height={height}
      role="img"
      aria-label={t('summaryCard.previewAlt', { name: goalName })}
    >
      <rect x={0} y={0} width={WIDTH} height={height} fill="#ffffff" />
      <text x={PADDING} y={PADDING + 24} fontSize={20} fontWeight="bold" fill="#1a1a1a">
        {goalName}
      </text>
      <text x={PADDING} y={PADDING + 46} fontSize={13} fill="#595959">
        {period.dateFrom}
        {rangeSeparator()}
        {period.dateTo}
      </text>
      {textLines.map((line, index) => (
        <g key={line.key}>
          <text x={PADDING} y={labelYs[index]} fontSize={13} fill="#898781">
            {line.label}
          </text>
          {renderLineValues(line, PADDING, labelYs[index])}
        </g>
      ))}
      {roadmapVisible && (
        <g transform={`translate(${PADDING}, ${height - ROADMAP_HEIGHT + 8})`}>
          <GoalRoadmapMini
            category={category}
            progressRatio={aggregate.roadmap.progress_ratio}
            isAchieved={aggregate.roadmap.is_achieved}
            overrunDays={aggregate.roadmap.overrun_days}
            size={{ width: WIDTH - PADDING * 2, height: ROADMAP_HEIGHT - 16 }}
          />
        </g>
      )}
    </svg>
  )
}
