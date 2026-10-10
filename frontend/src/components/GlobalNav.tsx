import { NavLink } from 'react-router-dom'
import { ROUTES } from '../constants/routes'
import { t } from '../locales/t'

const NAV_ITEMS = [
  { to: ROUTES.dashboard, labelKey: 'nav.dashboard' },
  { to: ROUTES.goals, labelKey: 'nav.goals' },
  { to: ROUTES.bookshelf, labelKey: 'nav.bookshelf' },
  { to: ROUTES.calendar, labelKey: 'nav.calendar' },
  { to: ROUTES.analytics, labelKey: 'nav.analytics' },
  { to: ROUTES.settings, labelKey: 'nav.settings' },
  { to: ROUTES.help, labelKey: 'nav.help' },
] as const

/** グローバルナビゲーション（仕様書5.1）。 */
export function GlobalNav() {
  return (
    <nav className="flex gap-1 border-b border-border bg-surface px-4 py-2">
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
