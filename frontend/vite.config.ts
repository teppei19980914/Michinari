// test セクションを型付きで書くため、defineConfig は 'vite' ではなく 'vitest/config' から
// 取り込む（'vite' の UserConfig は test を持たず tsc -b が失敗する）。
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // バックエンドの既定ポート（app_setting: server.port、backend/app/init/seed_data.py）。
      '/api': 'http://127.0.0.1:8100',
    },
  },
  test: {
    // コンポーネントの描画テスト（@testing-library/react）にDOMが要るため jsdom を使う。
    // 純粋関数のテストも同じ環境で問題なく動くため、ファイルごとの切り替えはしない。
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      // includeは「計測対象の絞り込み」ではなく「どのテストからも読み込まれないファイルを
      // 対象へ追加する」設定である（テスト中に読み込まれたファイルは常に計測される）。
      // src/**/*.ts を挙げているのは、テストを書き忘れた判定ロジックが 0% として表に
      // 現れるようにするため。計測したくないものは exclude 側に書く。
      // 分岐は .ts の純粋関数へ切り出すのが基本方針（CODING_RULES.md テストカバレッジ、
      // features/goal/closeGoalConfirm.ts が典型）だが、確認モーダルのように「押した結果
      // 何が送信されるか」まで含めて守りたい .tsx はテストを書いて100%まで到達させる。
      include: [
        'src/**/*.ts',
        'src/features/goal/CloseGoalModal.tsx',
        'src/features/goal/DeleteArchivedGoalModal.tsx',
        // 目標詳細のタブ群。いずれも「送信内容を決める判定」を持つため除外せず100%まで書く
        // （Phase 35。方針は OPERATIONS.md「フロントエンドのテストとカバレッジ」参照）。
        'src/features/goal/BasicInfoTab.tsx',
        'src/features/goal/BookTab.tsx',
        'src/features/goal/LoadProfileTab.tsx',
        'src/features/goal/MaterialsTab.tsx',
        // MaterialsTab から切り出した表示部品（Phase 36。1関数100行の上限への対応）。
        // 切り出し元と同じく、描画テストで100%まで到達させる。
        'src/features/goal/MaterialCard.tsx',
        'src/features/goal/MaterialFormFields.tsx',
        'src/features/goal/ResourceAllocationTab.tsx',
        'src/features/goal/SubjectsTab.tsx',
        'src/features/goal/WorkAssignmentTab.tsx',
        'src/features/goal/WorkReportTab.tsx',
        'src/components/Toast.tsx',
        // ダッシュボードの表示部品。送信は行わないが、目標種別ごとに出す指標が異なり
        // （資格試験＝計画管理、読書・仕事＝記録の継続）、取り違えても数字が並ぶため
        // 画面を見ても気づけない。種別ごとの出し分けをテストで固定する（Phase 35）。
        'src/features/dashboard/GoalCardList.tsx',
        'src/features/dashboard/StatsSummary.tsx',
        'src/features/dashboard/TodayMessage.tsx',
        'src/features/dashboard/TodayQuotaSection.tsx',
        'src/features/dashboard/TodayStatusSection.tsx',
        'src/features/dashboard/WarningBanner.tsx',
      ],
      exclude: [
        'src/**/*.test.ts',
        'src/**/*.test.tsx',
        // 描画テストの共通基盤（Provider で包む処理）。テストから常に読み込まれるため
        // include に挙げなくても計測対象に入ってしまうが、production へ出るコードではなく
        // テストコードの一部であるため除外する。
        'src/test/**',
        // 画面単位の描画テスト（DailyReportPage.test.tsx / DailyReportViewPage.test.tsx）が
        // 読み込む画面本体と入力欄。入力ハンドラを多数持つこれらを100%にするのは現実的で
        // ないため除外し、振る舞いの回帰検知は描画テストが、網羅率は判定ロジックを
        // 切り出した.ts側が担う。
        // ディレクトリ丸ごとではなく列挙するのは、features/record/ に置いた判定を含む.tsx
        // （CategoryReportSection.tsx）まで黙って計測外になるのを防ぐため。
        'src/pages/**/*.tsx',
        'src/features/record/*Fields.tsx',
        'src/features/record/*SummaryList.tsx',
        'src/features/record/ChatPanel.tsx',
        'src/features/record/CommentSection.tsx',
        'src/features/record/GoalTabBar.tsx',
        // 自動生成（openapi-typescript）。手で直さないため対象外。
        'src/types/**',
        // 型のみ・定数のみで分岐を持たないファイル。値を並べているだけの
        // errorCodes.ts・goalCategories.ts が該当する。queryKeys.ts（キャッシュキー）と
        // routes.ts（画面遷移パス）は値を組み立てる関数を持ち、崩れても型検査で表に出ない
        // （どちらも string）ため除外しない（Phase 33 の横展開チェックで判明）。
        'src/constants/errorCodes.ts',
        'src/constants/goalCategories.ts',
        // src/locales/ は除外しない。ja.json は文言のみだが include（src/**/*.ts）に一致
        // しないため自然に対象外となり、分岐（キー未解決時のフォールバック・{{var}}置換）を
        // 持つ t.ts だけが計測される。
        // エンドポイント単位のAPIラッパ。分岐を持たず、実通信なしでは意味のある検証に
        // ならないため対象外とする。同じ src/api/ でも client.ts は通信失敗の NETWORK_ERROR
        // への変換・204の扱い・エラーコードの既定値・未登録コードのフォールバックという分岐を
        // 持ち、全画面のエラー表示がここを通るため計測する。ディレクトリ丸ごとの除外にしない
        // のは、判定を含むファイルが黙って計測外になるのを防ぐため（features/record/ と同じ）。
        'src/api/!(client).ts',
        // Reactフック。呼び出しにコンポーネントのレンダリングが必要で、フック単体を直接
        // 検証しても実際の使われ方を再現できないため対象外（CODING_RULES.md「除外可」）。
        'src/**/use*.ts',
        // ブラウザAPI（document / URL.createObjectURL）に直接依存し、同じ理由で対象外。
        'src/utils/downloadBlob.ts',
      ],
      thresholds: {
        // 判定ロジック層は分岐まで100%を維持する（例外処理を除きカバレッジ100%を目指す方針）。
        lines: 100,
        branches: 100,
        functions: 100,
        statements: 100,
      },
    },
  },
})
