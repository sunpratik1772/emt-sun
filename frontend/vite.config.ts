import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

const previewMode = process.env.VITE_PREVIEW_MODE === 'true'

// Keep aliases here in sync with compilerOptions.paths in tsconfig.json.
export default defineConfig({
  plugins: [react()],
  envPrefix: ['VITE_', 'REACT_APP_'],
  test: {
    include: ['src/**/*.test.ts'],
  },
  optimizeDeps: {
    include: [
      'monaco-editor/esm/vs/editor/editor.api',
      'monaco-editor/esm/vs/basic-languages/yaml/yaml.contribution',
      'monaco-editor/esm/vs/language/json/monaco.contribution',
    ],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/reactflow') || id.includes('node_modules/@reactflow')) {
            return 'reactflow'
          }
          if (id.includes('node_modules/monaco-editor') || id.includes('node_modules/@monaco-editor')) {
            return 'monaco'
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@nodes': path.resolve(__dirname, 'src/nodes'),
      '@store': path.resolve(__dirname, 'src/store'),
      '@services': path.resolve(__dirname, 'src/services'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@styles': path.resolve(__dirname, 'src/styles'),
      '@types': path.resolve(__dirname, 'src/types'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: true,
    ...(previewMode
      ? {
          hmr: {
            clientPort: 443,
            protocol: 'wss',
          },
        }
      : {}),
    proxy: {
      '/api/run/stream': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Accept-Encoding', 'identity')
          })
        },
      },
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
