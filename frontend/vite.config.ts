import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

/**
 * Vite configuration.
 *
 * The dev server binds to 0.0.0.0 so it can be reached from outside the
 * container/sandbox. API calls are proxied to the Django backend, which
 * keeps the browser on a single origin (no CORS in development, and the
 * same relative-URL contract as production behind nginx).
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const devPort = Number(env.VITE_PORT ?? 5173);
  const apiTarget = env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000';

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '0.0.0.0',
      port: devPort,
      strictPort: true,
      // Allow the sandbox/preview proxy hosts; configure real hosts via env.
      allowedHosts: true,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/admin': { target: apiTarget, changeOrigin: true },
        '/static': { target: apiTarget, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'lcov'],
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/vite-env.d.ts'],
      },
    },
    preview: {
      host: '0.0.0.0',
      port: devPort,
      strictPort: true,
      allowedHosts: true,
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          // Split vendor code so app chunks stay small and cacheable.
          manualChunks(moduleId: string) {
            if (!moduleId.includes('node_modules')) return undefined;
            if (moduleId.includes('react-router') || /node_modules\/(react|react-dom|scheduler)\//.test(moduleId)) {
              return 'react';
            }
            if (moduleId.includes('@tanstack')) return 'query';
            if (moduleId.includes('lucide-react')) return 'icons';
            return 'vendor';
          },
        },
      },
    },
  };
});
