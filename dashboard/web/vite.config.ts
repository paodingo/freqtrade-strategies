import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/v2/",
  plugins: [react()],
  build: {
    outDir: "../public/v2",
    emptyOutDir: true,
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) => assetInfo.name?.endsWith(".css")
          ? "assets/app.css"
          : "assets/fonts/[name][extname]",
      },
    },
  },
});
