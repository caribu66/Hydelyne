import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { gzipSync } from 'node:zlib';
import path from 'path';
import type { Plugin } from 'vite';
import {defineConfig} from 'vite';

function gzipBundleBudget(): Plugin {
  const entryBudget = 150 * 1024;
  const asyncBudget = 100 * 1024;

  return {
    name: 'gzip-bundle-budget',
    generateBundle(_options, bundle) {
      const violations: string[] = [];

      for (const [fileName, output] of Object.entries(bundle)) {
        if (output.type !== 'chunk') continue;
        const gzipBytes = gzipSync(output.code).byteLength;
        const budget = output.isEntry ? entryBudget : asyncBudget;
        if (gzipBytes > budget) {
          violations.push(`${fileName} is ${(gzipBytes / 1024).toFixed(1)} KiB gzip (budget ${(budget / 1024).toFixed(0)} KiB)`);
        }
      }

      if (violations.length > 0) {
        this.error(`Bundle budget exceeded:\n${violations.join('\n')}`);
      }
    },
  };
}

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss(), gzipBundleBudget()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modify—file watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
    build: {
      chunkSizeWarningLimit: 250,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom'],
            apollo: ['@apollo/client', 'graphql'],
            motion: ['motion'],
            d3: ['d3'],
            vendor: ['lucide-react', '@google/genai'],
          },
        },
      },
    },
  };
});
