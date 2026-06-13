import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  build: {
    outDir: '../backend/static', // Compiles production chunks straight into the FastAPI backend folder
    emptyOutDir: true,
    minify: 'esbuild'
  }
});