import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { GoalRoadmapMini } from './GoalRoadmapMini'
import { CHARACTER_ICONS } from '../../constants/characterIcons'

describe('GoalRoadmapMini', () => {
  it('role="img"とaria-label（要約文言）を付ける', () => {
    const { getByRole } = render(
      <GoalRoadmapMini category="EXAM" progressRatio={0.5} isAchieved={false} overrunDays={3} />,
    )
    expect(getByRole('img', { name: '全体の50%、予定より3日遅れです' })).toBeTruthy()
  })

  it('読書・仕事は現在地が常にUI-01になる（§0 U7）', () => {
    const { container } = render(
      <GoalRoadmapMini category="READING" progressRatio={0.3} isAchieved={false} overrunDays={null} />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.normal)
  })

  it('達成時はUI-11を使う', () => {
    const { container } = render(
      <GoalRoadmapMini category="WORK" progressRatio={1} isAchieved overrunDays={null} />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.achieved)
  })

  it('境界値: progressRatioがnull（記録0件）でも破綻しない', () => {
    const { container } = render(
      <GoalRoadmapMini category="EXAM" progressRatio={null} isAchieved={false} overrunDays={null} />,
    )
    expect(container.querySelector('svg')).toBeTruthy()
  })
})
