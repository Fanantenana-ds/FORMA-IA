import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import type { Plugin } from 'vite';

const frontendErrorTerminal = (): Plugin => ({
  name: 'frontend-error-terminal',
  apply: 'serve',
  configureServer(server) {
    server.middlewares.use('/__frontend_error', (req, res) => {
      if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
      let body = '';
      req.on('data', (chunk: Buffer) => { body += chunk.toString(); if (body.length > 1024) req.destroy(); });
      req.on('end', () => {
        try {
          const report = JSON.parse(body);
          const safe = (value: unknown) => typeof value === 'string' && /^[\w./:-]{1,100}$/.test(value) ? value : '-';
          const status = Number.isInteger(report.status) ? report.status : '-';
          const line = Number.isInteger(report.line) ? report.line : '-';
          server.config.logger.warn(`[frontend] ${safe(report.kind)} ${safe(report.route)} ${status} ${safe(report.name)} ${safe(report.file)}:${line}`);
          res.statusCode = 204;
        } catch { res.statusCode = 400; }
        res.end();
      });
    });
  },
});

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = (env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  return {
    plugins: [react(), tailwindcss(), frontendErrorTerminal()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/health': { target: apiTarget, changeOrigin: true }
      },
    },
  };
});
