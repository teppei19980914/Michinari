import { defineConfig } from 'vite'
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
})
