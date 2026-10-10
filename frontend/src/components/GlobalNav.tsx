import { NavLink } from 'react-router-dom'
import { ROUTES } from '../constants/routes'
import { t } from '../locales/t'
import { useHeaderVisibility } from './headerVisibilityContext'

const NAV_ITEMS = [
  { to: ROUTES.dashboard, labelKey: 'nav.dashboard' },
  { to: ROUTES.goals, labelKey: 'nav.goals' },
  { to: ROUTES.bookshelf, labelKey: 'nav.bookshelf' },
  { to: ROUTES.calendar, labelKey: 'nav.calendar' },
  { to: ROUTES.analytics, labelKey: 'nav.analytics' },
  { to: ROUTES.settings, labelKey: 'nav.settings' },
  { to: ROUTES.help, labelKey: 'nav.help' },
] as const

/** グローバルナビゲーション（仕様書5.1）。下スクロールで隠れ、上スクロールで即座に現れる
 * （UIリッチ化）。固定高さは`--global-nav-height`（index.css）で一元管理し、
 * `App.tsx`のLayoutのpadding-topと二重管理にならないようにしている。 */
export function GlobalNav() {
  const visible = useHeaderVisibility()
  return (
    <nav
      className={`fixed inset-x-0 top-0 z-20 flex gap-1 border-b border-border bg-surface px-4 py-2 transition-transform duration-200 ease-in-out ${
        visible ? 'translate-y-0' : '-translate-y-full'
      }`}
    >
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === ROUTES.dashboard}
          className={({ isActive }) =>
            `rounded-md px-3 py-1.5 text-sm font-medium ${
              isActive
                ? 'bg-accent-muted-bg text-accent-muted-text'
                : 'text-text-muted hover:bg-surface-muted'
            }`
          }
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}
