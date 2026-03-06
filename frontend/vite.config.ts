/**
 * Vite Configuration
 * ==================
 * 
 * Build tool configuration for React + TypeScript.
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  appType: 'spa', // Serves index.html for all unmatched routes (SPA fallback for /strategy-builder, /backtesting)
  server: {
    port: 8081,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
