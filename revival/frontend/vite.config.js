import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": { target: proxyTarget, changeOrigin: true },
      "/webhooks": { target: proxyTarget, changeOrigin: true },
    },
    watch: { usePolling: true, interval: 500 },
  },
});
