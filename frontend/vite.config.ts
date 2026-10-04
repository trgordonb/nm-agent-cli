import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies /api and /wapi (in-process wiki engine) to the FastAPI
// backend (server.py, port 8000).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/wapi": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
