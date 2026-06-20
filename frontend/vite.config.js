import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SPA build. Env vars are injected at build time via VITE_* (see .env.example).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: false },
});
