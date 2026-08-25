import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server explicitly pinned to 5173 to match the backend's
// CORS_ALLOWED_ORIGINS default (http://localhost:5173). If you change
// this port, update CORS_ALLOWED_ORIGINS in the backend .env too, or
// every request will fail CORS with a console error that looks nothing
// like "wrong port."
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
