import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: process.env.VITE_USE_PROXY === 'true' ? {
            '/run': {
                target: process.env.VITE_AGENT_PROXY_TARGET || 'http://127.0.0.1:8003',
                changeOrigin: true,
            },
        } : undefined,
    },
})
