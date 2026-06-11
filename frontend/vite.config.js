import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
  ],
  
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    target: 'es2020',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
        pure_funcs: ['console.info', 'console.debug'],
      },
      format: {
        comments: false,
      },
    },
    
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        
        manualChunks: {
          'vendor-react': [
            'react',
            'react-dom',
            'react-router-dom',
          ],
          'three-3d': [
            'three',
            '@react-three/fiber',
            '@react-three/drei',
          ],
          'state': [
            'zustand',
          ],
          'http': [
            'axios',
          ],
        },
        hashCharacters: 'base64',
        experimentalMinChunkSize: 10000,
      },
    },
    assetsInlineLimit: 4096,
    cssCodeSplit: true,
    reportCompressedSize: true,
  },
  
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  
  preview: {
    port: 4173,
  },
  
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'three',
      '@react-three/fiber',
      '@react-three/drei',
      'zustand',
      'axios',
    ],
  },
})
