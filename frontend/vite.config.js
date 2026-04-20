import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// When running inside Docker, set VITE_PROXY_TARGET=http://host.docker.internal:8000
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
    watch: {
      // Polling is needed for file changes to be detected from a Windows host mount
      usePolling: true,
      interval: 500,
    },
  },
});
