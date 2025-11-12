import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // This is the CRITICAL section for redirecting API calls.
    proxy: {
      // Redirects requests starting with /api to the Node.js server
      '/api': {
        target: 'http://localhost:3000', // The address of your running backend
        changeOrigin: true, 
        secure: false, 
      },
    },
    // Ensures Vite starts correctly when running via concurrently
    host: '0.0.0.0', 
  }
});