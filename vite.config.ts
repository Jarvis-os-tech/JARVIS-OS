import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    root: path.resolve(__dirname, 'ui/web'),
    publicDir: path.resolve(__dirname, 'ui/web/public'),
    build: {
      outDir: path.resolve(__dirname, 'dist'),
      emptyOutDir: true,
    },
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'ui/web/src'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/live-voice': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
        },
        '/live': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
        },
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
        },
      },
      watch: {
        ignored: [
          '**/memory/**',
          '**/jarvis-memory/**',
          '**/.agents/**',
          '**/.gemini/**',
          '**/dist/**',
          '**/brain/**',
          '**/skills/**',
          '**/gateway/**',
          '**/tools/**',
          '**/data/**',
          '**/.venv/**',
          '**/.git/**',
          '**/*.log',
        ],
      },
    },
  };
});
