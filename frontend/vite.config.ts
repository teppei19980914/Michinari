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
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      // 計測対象は判定ロジックを置く .ts のみとする。.tsx（コンポーネント）は jsdom /
      // @testing-library を導入していないため描画テストを書けず、計測しても 0% が並んで
      // 実際の穴が埋もれる。分岐は .ts の純粋関数へ切り出す方針（CODING_RULES.md
      // テストカバレッジ、features/goal/closeGoalConfirm.ts が典型）。
      include: ['src/**/*.ts'],
      exclude: [
        'src/**/*.test.ts',
        // 自動生成（openapi-typescript）。手で直さないため対象外。
        'src/types/**',
        // 型のみ・定数のみで分岐を持たないファイル。
        'src/constants/**',
        'src/locales/**',
        // API 呼び出しの薄いラッパ（分岐を持たず、実通信なしでは意味のある検証にならない）。
        'src/api/**',
        // Reactフック。描画基盤（jsdom / @testing-library）が無いと呼び出せないため対象外
        // （CODING_RULES.md「除外可」。導入時は .tsx とあわせて対象へ戻す）。
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
