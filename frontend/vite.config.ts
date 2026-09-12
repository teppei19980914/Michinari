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
      // 計測対象は判定ロジックを置く .ts と、描画テストを書いた .tsx とする。
      // 分岐は .ts の純粋関数へ切り出すのが基本方針（CODING_RULES.md テストカバレッジ、
      // features/goal/closeGoalConfirm.ts が典型）だが、確認モーダルのように「押した結果
      // 何が送信されるか」まで含めて守りたいものは .tsx 側もテストして対象へ加える。
      // 未計測の .tsx を一括で対象にすると 0% が大量に並んで実際の穴が埋もれるため、
      // テストを書いたものから個別に追加していく。
      include: [
        'src/**/*.ts',
        'src/features/goal/CloseGoalModal.tsx',
        'src/features/goal/DeleteArchivedGoalModal.tsx',
        'src/components/Toast.tsx',
        'src/features/dashboard/TodayStatusSection.tsx',
      ],
      exclude: [
        'src/**/*.test.ts',
        // 自動生成（openapi-typescript）。手で直さないため対象外。
        'src/types/**',
        // 型のみ・定数のみで分岐を持たないファイル。
        'src/constants/**',
        'src/locales/**',
        // API 呼び出しの薄いラッパ（分岐を持たず、実通信なしでは意味のある検証にならない）。
        'src/api/**',
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
