import { build } from "vite";

// AutoImport and Components generate the declaration files consumed by vue-tsc.
// Running a no-write Vite build makes type checking deterministic on clean clones and CI.
await build({
  mode: "development",
  logLevel: "warn",
  build: {
    write: false,
    emptyOutDir: false,
  },
});
