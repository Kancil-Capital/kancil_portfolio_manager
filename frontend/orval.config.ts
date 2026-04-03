import { defineConfig } from "orval";

export default defineConfig({
  kancilApi: {
    input: {
      target: "./openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "./lib/generated",
      client: "swr",
      override: {
        mutator: {
          path: "./lib/fetcher.ts",
          name: "fetcher",
        },
      },
    },
  },
});
