import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Render gibi static hosting ortamlarında dosya yollarını düzeltir
  build: {
    outDir: 'dist', // Vite'in build çıktısının gideceği klasör
    emptyOutDir: true, // Eski build dosyalarını temizler (isteğe bağlı ama önerilir)
  },
  server: {
    port: 5173, // Lokal geliştirme için (npm run dev)
    open: true, // Tarayıcıyı otomatik açar
  },
})
