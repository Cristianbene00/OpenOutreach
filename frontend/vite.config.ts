import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built bundle is served by Django: index.html is loaded as a template and
// hashed assets live under /static/ (frontend/dist is on STATICFILES_DIRS).
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    manifest: true,
  },
  server: {
    port: 5173,
    // Dev server proxies API + admin to Django so `make frontend-dev` works
    // against a running `make web`.
    proxy: {
      "/api": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
});
