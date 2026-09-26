import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['json', 'text'],
      include: [
        'src/features/bookshelf/**/*.ts',
        'src/features/bookshelf/**/*.tsx',
      ],
      reportOnFailure: true,
    },
  },
})
