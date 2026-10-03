/** LoadingOverlay（仕様書v1.1 13章）の描画テスト。
 *
 * useMutationのmeta.overlayをTanStack Queryのミューテーションキャッシュ経由で横断的に
 * 監視する実装のため、実際にuseMutationを呼ぶ最小限のTriggerコンポーネントを介して
 * pending状態を作る（モックでは実装の要である「キャッシュ横断監視」自体を検証できない）。 */
import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useMutation } from '@tanstack/react-query'
import { t } from '../locales/t'
import { LoadingOverlay } from './LoadingOverlay'
import type { OverlayKind } from '../constants/characterIcons'

/** resolve/rejectを外側から制御できるPromiseを作る（mutationFnをpendingのまま保持するため）。 */
function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

function Trigger({
  overlay,
  onReady,
}: {
  overlay?: OverlayKind
  onReady: (mutate: () => void) => void
}) {
  const deferred = createDeferred<void>()
  const mutation = useMutation({
    mutationFn: () => deferred.promise,
    meta: overlay ? { overlay } : undefined,
  })
  onReady(() => mutation.mutate())
  return null
}

function renderScenario(triggers: Array<{ overlay?: OverlayKind }>) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const mutates: Array<() => void> = []
  render(
    <QueryClientProvider client={queryClient}>
      {triggers.map((trigger, index) => (
        <Trigger
          key={index}
          overlay={trigger.overlay}
          onReady={(mutate) => {
            mutates[index] = mutate
          }}
        />
      ))}
      <LoadingOverlay />
    </QueryClientProvider>,
  )
  return mutates
}

afterEach(() => cleanup())

describe('LoadingOverlay', () => {
  it('renders nothing when no mutation is pending', () => {
    renderScenario([{ overlay: 'saving' }])

    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows the saving message while a meta.overlay="saving" mutation is pending', async () => {
    const [mutate] = renderScenario([{ overlay: 'saving' }])

    act(() => mutate())

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())
    expect(screen.getByText(t('common.overlay.saving'))).toBeTruthy()
  })

  it('shows the deleting message while a meta.overlay="deleting" mutation is pending', async () => {
    const [mutate] = renderScenario([{ overlay: 'deleting' }])

    act(() => mutate())

    await waitFor(() => expect(screen.getByText(t('common.overlay.deleting'))).toBeTruthy())
  })

  it('does not show the overlay for a mutation without meta.overlay', async () => {
    const [mutate] = renderScenario([{}])

    act(() => mutate())

    // pendingにはなるがoverlayを持たないため、待っても出現しないことを確認する
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('prioritizes the deleting message when saving and deleting are pending at the same time', async () => {
    const [mutateSaving, mutateDeleting] = renderScenario([
      { overlay: 'saving' },
      { overlay: 'deleting' },
    ])

    act(() => {
      mutateSaving()
      mutateDeleting()
    })

    await waitFor(() => expect(screen.getByText(t('common.overlay.deleting'))).toBeTruthy())
    expect(screen.queryByText(t('common.overlay.saving'))).toBeNull()
  })

  it('hides the overlay again once the mutation settles', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    })
    function ResolvableTrigger({
      onMutateReady,
      onResolveReady,
    }: {
      onMutateReady: (mutate: () => void) => void
      onResolveReady: (resolve: () => void) => void
    }) {
      const mutation = useMutation({
        mutationFn: () => new Promise<void>((resolve) => onResolveReady(resolve)),
        meta: { overlay: 'saving' },
      })
      onMutateReady(() => mutation.mutate())
      return null
    }
    let mutate: (() => void) | undefined
    let resolveMutation: (() => void) | undefined
    render(
      <QueryClientProvider client={queryClient}>
        <ResolvableTrigger
          onMutateReady={(m) => {
            mutate = m
          }}
          onResolveReady={(r) => {
            resolveMutation = r
          }}
        />
        <LoadingOverlay />
      </QueryClientProvider>,
    )
    if (!mutate) {
      throw new Error('ResolvableTriggerの初期化に失敗しました')
    }

    act(() => mutate!())
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())

    if (!resolveMutation) {
      throw new Error('mutationFnが実行されていません')
    }
    act(() => resolveMutation!())
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  })
})
