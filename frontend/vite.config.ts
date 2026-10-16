import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: resolve(__dirname, "../src/recurrence/static/recurrence/js"),
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
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
