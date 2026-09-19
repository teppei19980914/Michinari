/** AI接続手順の段階的な案内（仕様書6.11）。Hostの有無でリンクの出し分けが変わる点を固定する。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { AiConnectionGuide } from './AiConnectionGuide'

afterEach(() => {
  cleanup()
})

describe('AiConnectionGuide', () => {
  it('links to the tenant host once it is entered', () => {
    render(<AiConnectionGuide host="example.newton-x.net" />)

    const link = screen.getByRole('link', { name: t('settings.aiConnection.guide.step1LinkLabel') })
    expect(link.getAttribute('href')).toBe('https://example.newton-x.net')
  })

  it('shows a hint instead of a link before the host is entered', () => {
    render(<AiConnectionGuide host="" />)

    expect(screen.queryByRole('link')).toBe(null)
    expect(screen.getByText(t('settings.aiConnection.guide.step1HostMissing'))).toBeTruthy()
  })

  it('explains what an access token is in plain language', () => {
    render(<AiConnectionGuide host="" />)

    expect(screen.getByText(t('settings.aiConnection.guide.whatIsPatDescription'))).toBeTruthy()
  })
})
