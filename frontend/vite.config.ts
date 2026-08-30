import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173; proxy /api to the backend on 8000 to avoid CORS fuss.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
