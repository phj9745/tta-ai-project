import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // ▼▼▼ 여기부터 추가된 부분 ▼▼▼
  server: {
    host: '0.0.0.0',    // 외부(Nginx 컨테이너)에서 접속 가능하게 설정
    allowedHosts: true, // 모든 도메인/IP 허용 (보안 검사 비활성화)
  },
  // ▲▲▲ 여기까지 추가된 부분 ▲▲▲

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})