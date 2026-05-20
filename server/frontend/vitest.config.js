import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.js"],
    include: ["tests/**/*.{test,spec}.{js,ts}"],
    exclude: [
      "tests/setup.js",
      "tests/fixtures.js",
      "node_modules/**",
      "dist/**",
    ],
    server: {
      deps: {
        inline: ["floating-vue"],
      },
    },
    coverage: {
      provider: "v8",
      include: ["src/**/*.{js,jsx,vue}"],
      exclude: ["tests/**", "coverage/**", "dist/**", "webpack.*.js"],
    },
  },
});
