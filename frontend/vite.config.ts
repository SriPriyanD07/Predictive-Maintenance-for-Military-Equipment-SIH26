import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The /api proxy means the browser only ever talks to the Vite origin, so no
// cross-origin request is made. backend/main.py restricts allow_origins to
// port 5173, and this way that list needs no change.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
