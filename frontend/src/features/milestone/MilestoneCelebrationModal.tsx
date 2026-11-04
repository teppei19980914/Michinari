import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import { t } from '../../locales/t'
import { resolveMilestoneIcon, resolveMilestoneMessage } from './milestoneContent'
import type { QueuedMilestone } from './useMilestoneCelebrationQueue'

//: 紙吹雪の配置（左位置%・色・開始の遅れ）。固定の装飾色のため明暗共通で直書きしてよい
//: （CODING_RULES.md「目標種別バッジ等『意味を持つ固定色』は例外」と同じ扱い）。
const CONFETTI_PIECES: readonly { left: number; color: string; delaySeconds: number }[] = [
  { left: 6, color: '#F59E0B', delaySeconds: 0 },
  { left: 16, color: '#3B82F6', delaySeconds: 0.15 },
  { left: 26, color: '#EC4899', delaySeconds: 0.3 },
  { left: 38, color: '#10B981', delaySeconds: 0.05 },
  { left: 50, color: '#F59E0B', delaySeconds: 0.25 },
  { left: 62, color: '#3B82F6', delaySeconds: 0.1 },
  { left: 74, color: '#EC4899', delaySeconds: 0.35 },
  { left: 84, color: '#10B981', delaySeconds: 0.2 },
  { left: 94, color: '#F59E0B', delaySeconds: 0.4 },
]

type MilestoneCelebrationModalProps = {
  milestone: QueuedMilestone | undefined
  onClose: () => void
}

/** 節目のお祝いモーダル（開発Todo_節目のお祝い_v1.0 M5・M7）。トーストではなく手動で
 * 閉じるモーダルを使い、既存のキャラクターアイコン＋CSSアニメーション（紙吹雪風）で
 * 特別感を出す。新規イラストは追加しない。 */
export function MilestoneCelebrationModal({ milestone, onClose }: MilestoneCelebrationModalProps) {
  const prefersReducedMotion = usePrefersReducedMotion()

  return (
    <Modal open={milestone != null} onClose={onClose} title={t('milestone.celebration.title')}>
      {milestone && (
        <div className="relative flex flex-col items-center gap-4 overflow-hidden py-2">
          {!prefersReducedMotion &&
            CONFETTI_PIECES.map((piece, index) => (
              <span
                key={index}
                className="milestone-confetti-piece"
                style={{
                  left: `${piece.left}%`,
                  backgroundColor: piece.color,
                  animationDelay: `${piece.delaySeconds}s`,
                }}
              />
            ))}
          <img
            src={CHARACTER_ICONS[resolveMilestoneIcon(milestone.category)]}
            alt=""
            className="h-24 w-24"
          />
          <p className="text-center text-base font-medium text-text-primary">
            {resolveMilestoneMessage(milestone.achievement)}
          </p>
          <Button type="button" onClick={onClose}>
            {t('milestone.celebration.closeButton')}
          </Button>
        </div>
      )}
    </Modal>
  )
}
