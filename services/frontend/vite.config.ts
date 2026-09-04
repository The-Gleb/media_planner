import { randomUUID } from 'node:crypto'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/planner-api': {
        target: process.env.PLANNER_URL ?? 'http://127.0.0.1:8082',
        changeOrigin: true,
        timeout: 20_000,
        proxyTimeout: 20_000,
        configure: (proxy) => proxy.on('proxyReq', (request) => {
          if (!request.hasHeader('X-Request-ID')) request.setHeader('X-Request-ID', randomUUID())
        }),
        rewrite: (path) => path.replace(/^\/planner-api/, ''),
      },
      '/api': {
        target: process.env.SIMULATOR_URL ?? 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
