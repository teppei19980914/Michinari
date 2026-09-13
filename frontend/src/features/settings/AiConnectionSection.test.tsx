/** AI接続設定（仕様書6.11）の表示と送信内容を固定する回帰テスト（Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で認証状況とアシスタント
 * 選択を切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * この画面は用途ごとのアシスタントを一覧から選ばせる（Phase7完了条件「識別子の手入力を
 * 求めない」）。用途と選択欄の対応が崩れても画面には同じ形の選択欄が並ぶだけで気づけず、
 * 日次フィードバックに週次要約のアシスタントが使われるといった事故になる。再認証の成否
 * 表示も、失敗を成功と伝えると利用者が原因に辿り着けない。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AiAssistantRead, AiStatusRead } from '../../api/ai'
import type { AppSettingsRead } from '../../api/settings'
import { AiConnectionSection } from './AiConnectionSection'

const getAiStatus = vi.hoisted(() => vi.fn())
const listAssistants = vi.hoisted(() => vi.fn())
const loginAi = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus, listAssistants, loginAi }))

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

const ASSISTANT_A: AiAssistantRead = { uid: 'uid-a', name: 'アシスタントA' }
const ASSISTANT_B: AiAssistantRead = { uid: 'uid-b', name: 'アシスタントB' }

const HOST = 'https://ai.example.test'

function makeAiConnection(
  overrides: Partial<AppSettingsRead['ai_connection']> = {},
): AppSettingsRead['ai_connection'] {
  return {
    host: HOST,
    client_id: '',
    tenant_id: '',
    api_base_url: '',
    assistant_uid_daily_feedback: '',
    assistant_uid_daily_feedback_reading: '',
    assistant_uid_weekly_summary: '',
    assistant_uid_daily_message: '',
    assistant_uid_goal_retrospective: '',
    assistant_uid_goal_retrospective_reading: '',
    folder_prefix: 'michinari',
    timeout_seconds: 60,
    min_interval_seconds: 3,
    ...overrides,
  }
}

function makeStatus(overrides: Partial<AiStatusRead> = {}): AiStatusRead {
  return { authenticated: true, model_status: {}, login_in_progress: false, ...overrides }
}

// --- 要素アクセサ ---
const hostInput = () => screen.getByLabelText(t('settings.aiConnection.hostLabel'))
const patInput = () => screen.getByLabelText(t('settings.aiConnection.authStatus.patLabel'))
const reauthButton = () =>
  screen.getByRole('button', { name: t('settings.aiConnection.authStatus.reauth') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const assistantSelect = (labelKey: string) => screen.getByLabelText(t(labelKey))

async function renderSection(
  settings: Partial<AppSettingsRead['ai_connection']> = {},
  { assistants = [ASSISTANT_A, ASSISTANT_B], status = makeStatus() } = {},
) {
  listAssistants.mockResolvedValue(assistants)
  getAiStatus.mockResolvedValue(status)
  const result = renderWithProviders(
    <AiConnectionSection settings={{ ai_connection: makeAiConnection(settings) } as AppSettingsRead} />,
  )
  await screen.findByText(t('settings.aiConnection.title'))
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
  loginAi.mockResolvedValue({ authenticated: true })
})

afterEach(() => {
  cleanup()
})

describe('AiConnectionSection の認証状況', () => {
  it('reports that the connection is authenticated', async () => {
    await renderSection()
    expect(
      await screen.findByText(t('settings.aiConnection.authStatus.authenticated')),
    ).toBeTruthy()
  })

  it('reports that the connection is not authenticated', async () => {
    await renderSection({}, { status: makeStatus({ authenticated: false }) })
    expect(
      await screen.findByText(t('settings.aiConnection.authStatus.notAuthenticated')),
    ).toBeTruthy()
  })

  it('notes a login that is still in progress', async () => {
    await renderSection({}, { status: makeStatus({ login_in_progress: true }) })
    expect(
      await screen.findByText(t('settings.aiConnection.authStatus.loginInProgress')),
    ).toBeTruthy()
  })

  it('hides the model status while the server reports none', async () => {
    await renderSection()
    await screen.findByText(t('settings.aiConnection.authStatus.authenticated'))
    expect(screen.queryByText(t('settings.aiConnection.modelStatusTitle'))).toBe(null)
  })

  it('marks each model as reachable or not', async () => {
    await renderSection({}, { status: makeStatus({ model_status: { 'model-x': true, 'model-y': false } }) })
    expect(await screen.findByText('model-x: ✓')).toBeTruthy()
    expect(screen.getByText('model-y: ×')).toBeTruthy()
  })
})

describe('AiConnectionSection の再認証', () => {
  it('keeps the reauth button disabled until a token is entered', async () => {
    const user = userEvent.setup()
    await renderSection()
    expect((reauthButton() as HTMLButtonElement).disabled).toBe(true)
    await user.type(patInput(), 'p')
    expect((reauthButton() as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps the token out of the visible text', async () => {
    await renderSection()
    // 個人アクセストークンは画面に出さない（パスワード欄として扱う）。
    expect(patInput().getAttribute('type')).toBe('password')
  })

  it('logs in with the entered host and token', async () => {
    const user = userEvent.setup()
    await renderSection()
    await user.type(patInput(), 'p')
    await user.click(reauthButton())

    await waitFor(() => expect(loginAi).toHaveBeenCalledOnce())
    expect(loginAi).toHaveBeenCalledWith({ host: HOST, personal_access_token: 'p' })
  })

  it('sends null for the host when it was cleared', async () => {
    const user = userEvent.setup()
    await renderSection()
    await user.clear(hostInput())
    await user.type(patInput(), 'p')
    await user.click(reauthButton())

    await waitFor(() => expect(loginAi).toHaveBeenCalledOnce())
    expect(loginAi.mock.calls[0][0].host).toBeNull()
  })

  it('tells the user the reauth succeeded', async () => {
    const user = userEvent.setup()
    await renderSection()
    await user.type(patInput(), 'p')
    await user.click(reauthButton())

    expect(
      await screen.findByText(t('settings.aiConnection.authStatus.reauthSucceeded')),
    ).toBeTruthy()
  })

  it('tells the user the reauth failed', async () => {
    // 失敗を成功と伝えると、利用者は原因に辿り着けない。
    const user = userEvent.setup()
    loginAi.mockResolvedValue({ authenticated: false })
    await renderSection()
    await user.type(patInput(), 'p')
    await user.click(reauthButton())

    expect(
      await screen.findByText(t('settings.aiConnection.authStatus.reauthFailed')),
    ).toBeTruthy()
  })

  it('clears the token field after a successful reauth', async () => {
    const user = userEvent.setup()
    await renderSection()
    await user.type(patInput(), 'p')
    await user.click(reauthButton())

    await waitFor(() => expect((patInput() as HTMLInputElement).value).toBe(''))
  })
})

describe('AiConnectionSection のアシスタント選択', () => {
  it('notes that the assistant list is still loading', async () => {
    listAssistants.mockReturnValue(new Promise(() => undefined))
    getAiStatus.mockResolvedValue(makeStatus())
    renderWithProviders(
      <AiConnectionSection settings={{ ai_connection: makeAiConnection() } as AppSettingsRead} />,
    )
    expect(screen.getByText(t('settings.aiConnection.assistant.loading'))).toBeTruthy()
  })

  it('warns when the assistant list cannot be read', async () => {
    listAssistants.mockRejectedValue(new Error('boom'))
    getAiStatus.mockResolvedValue(makeStatus())
    renderWithProviders(
      <AiConnectionSection settings={{ ai_connection: makeAiConnection() } as AppSettingsRead} />,
    )
    expect(
      await screen.findByText(t('settings.aiConnection.assistant.loadFailed')),
    ).toBeTruthy()
  })

  it('offers every assistant for every purpose', async () => {
    await renderSection()
    await screen.findByText(t('settings.aiConnection.authStatus.authenticated'))
    // 6用途 × (未設定 + アシスタント2件)。
    expect(screen.getAllByRole('option').length).toBe(6 * 3)
  })

  it('drops the unset placeholder once a purpose has an assistant', async () => {
    await renderSection({ assistant_uid_daily_feedback: ASSISTANT_A.uid })
    await screen.findByText(t('settings.aiConnection.authStatus.authenticated'))
    // 設定済みの1用途だけ「未設定」が消える。
    expect(screen.getAllByText(t('common.unset')).length).toBe(5)
  })

  it('saves the assistant against the purpose it was chosen for', async () => {
    // 用途と選択欄の対応が崩れると、日次フィードバックに別用途のアシスタントが使われる。
    const user = userEvent.setup()
    await renderSection()
    await waitFor(() => expect(listAssistants).toHaveBeenCalled())

    await user.selectOptions(
      assistantSelect('settings.aiConnection.assistant.dailyFeedbackReading'),
      ASSISTANT_B.uid,
    )
    await user.click(saveButton())

    await waitFor(() => expect(updateSettings).toHaveBeenCalledOnce())
    const sent = updateSettings.mock.calls[0][0].ai_connection
    expect(sent.assistant_uid_daily_feedback_reading).toBe(ASSISTANT_B.uid)
    expect(sent.assistant_uid_daily_feedback).toBe('')
  })
})

describe('AiConnectionSection の保存', () => {
  it('saves the connection parameters as edited', async () => {
    const user = userEvent.setup()
    await renderSection()

    await user.clear(screen.getByLabelText(t('settings.aiConnection.folderPrefixLabel')))
    await user.type(screen.getByLabelText(t('settings.aiConnection.folderPrefixLabel')), 'x')
    await user.clear(screen.getByLabelText(t('settings.aiConnection.timeoutSecondsLabel')))
    await user.type(screen.getByLabelText(t('settings.aiConnection.timeoutSecondsLabel')), '9')
    await user.clear(screen.getByLabelText(t('settings.aiConnection.minIntervalSecondsLabel')))
    await user.type(screen.getByLabelText(t('settings.aiConnection.minIntervalSecondsLabel')), '5')
    await user.click(saveButton())

    await waitFor(() => expect(updateSettings).toHaveBeenCalledOnce())
    expect(updateSettings.mock.calls[0][0].ai_connection).toMatchObject({
      folder_prefix: 'x',
      // 秒数は文字列ではなく数値で送る。
      timeout_seconds: 9,
      min_interval_seconds: 5,
    })
  })

  it('reports that the save succeeded', async () => {
    const user = userEvent.setup()
    await renderSection()
    await user.click(saveButton())

    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })
})
