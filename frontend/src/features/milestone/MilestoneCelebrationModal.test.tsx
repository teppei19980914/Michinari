import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MilestoneCelebrationModal } from './MilestoneCelebrationModal'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import type { QueuedMilestone } from './useMilestoneCelebrationQueue'
import type { MilestoneAchievement } from '../../api/milestones'

vi.mock('../../hooks/usePrefersReducedMotion')

function makeMilestone(overrides: Partial<MilestoneAchievement> = {}): QueuedMilestone {
  return {
    category: 'EXAM',
    achievement: {
      id: 1,
      goal_id: 10,
      milestone_type: 'CONSECUTIVE_DAYS',
      milestone_key: '7',
      achieved_at: '2026-01-01T00:00:00',
      celebrated_at: null,
      ...overrides,
    },
  }
}

describe('MilestoneCelebrationModal', () => {
  it('renders nothing when there is no milestone', () => {
    vi.mocked(usePrefersReducedMotion).mockReturnValue(false)
    render(<MilestoneCelebrationModal milestone={undefined} onClose={vi.fn()} />)

    expect(screen.queryByRole('button')).toBe(null)
  })

  it('shows the message and icon for the current milestone', () => {
    vi.mocked(usePrefersReducedMotion).mockReturnValue(false)
    render(<MilestoneCelebrationModal milestone={makeMilestone()} onClose={vi.fn()} />)

    expect(screen.queryByText(/7/)).not.toBe(null)
  })

  it('calls onClose when the close button is clicked', () => {
    vi.mocked(usePrefersReducedMotion).mockReturnValue(false)
    const onClose = vi.fn()
    render(<MilestoneCelebrationModal milestone={makeMilestone()} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: /閉じる/ }))

    expect(onClose).toHaveBeenCalled()
  })

  it('does not render confetti pieces when the user prefers reduced motion', () => {
    vi.mocked(usePrefersReducedMotion).mockReturnValue(true)
    const { container } = render(
      <MilestoneCelebrationModal milestone={makeMilestone()} onClose={vi.fn()} />,
    )

    expect(container.querySelectorAll('.milestone-confetti-piece')).toHaveLength(0)
  })

  it('renders confetti pieces when motion is not reduced', () => {
    vi.mocked(usePrefersReducedMotion).mockReturnValue(false)
    const { container } = render(
      <MilestoneCelebrationModal milestone={makeMilestone()} onClose={vi.fn()} />,
    )

    expect(container.querySelectorAll('.milestone-confetti-piece').length).toBeGreaterThan(0)
  })
})
