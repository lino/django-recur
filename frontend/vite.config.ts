import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: resolve(import.meta.dirname, "../src/recurrence/static/recurrence/js"),
    emptyOutDir: false,
    lib: {
      entry: resolve(import.meta.dirname, "src/index.ts"),
      name: "recurrence",
      formats: ["iife"],
      fileName: () => "recurrence-widget.js",
    },
    rollupOptions: {
      output: {
        extend: true,
      },
    },
  },
  test: {
    environment: "jsdom",
  },
});
