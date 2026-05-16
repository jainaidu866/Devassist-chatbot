import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: [
      'all',
      '.ngrok-free.app',
      '.ngrok-free.dev',
      'staleness-gratified-alright.ngrok-free.dev',
    ],
  },
})