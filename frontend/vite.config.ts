import { defineConfig,loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({mode})=>({
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  preview:{proxy:{'/runtime':{
    target:loadEnv(mode,'.','VITE_').VITE_API_BASE_URL??'http://127.0.0.1:8000',
    changeOrigin:true,rewrite:path=>path.replace(/^\/runtime/,'')
  }}},
  build: { rolldownOptions: { output: { manualChunks: (id: string) => {
    if (id.includes('node_modules') && /three|react-three/.test(id)) return 'three-vendor';
    if (id.includes('node_modules') && /[\\/]react(?:-dom)?[\\/]/.test(id)) return 'react-vendor';
  } } } }
}));
