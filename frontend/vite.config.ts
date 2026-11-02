import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
const proxy={'/api':{target:process.env.PREVIEW_API_TARGET||'http://127.0.0.1:8000',changeOrigin:true}};
export default defineConfig({plugins:[react()],server:{proxy},preview:{proxy},build:{rollupOptions:{output:{manualChunks(id){if(id.includes('/node_modules/@clerk/'))return 'identity';if(id.includes('/node_modules/@supabase/'))return 'sync'}}}}});
