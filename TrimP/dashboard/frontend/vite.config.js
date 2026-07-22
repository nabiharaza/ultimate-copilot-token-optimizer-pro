import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Split rarely-changing vendor code into its own chunk(s) so the
        // browser can fetch/parse it in parallel with app code and — more
        // importantly — cache it across deploys where only app code changes.
        // recharts is the single biggest dependency (pulls in d3 internals);
        // isolating it stops every UI tweak from invalidating its cache entry.
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-charts': ['recharts'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
    chunkSizeWarningLimit: 300,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:7432',
      '/ws': { target: 'ws://localhost:7432', ws: true },
    },
  },
})
