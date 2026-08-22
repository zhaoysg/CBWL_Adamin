import { createRequire } from "node:module";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, type PluginOption } from "vite";

const require = createRequire(import.meta.url);
type UniPluginFactory = () => PluginOption[];
type ModuleWithDefault = { default?: unknown };

function resolveUniPluginFactory(moduleValue: unknown): UniPluginFactory {
  let candidate = moduleValue;
  for (let depth = 0; depth < 3; depth += 1) {
    if (typeof candidate === "function") return candidate as UniPluginFactory;
    if (candidate && typeof candidate === "object" && "default" in candidate) {
      candidate = (candidate as ModuleWithDefault).default;
      continue;
    }
    break;
  }
  throw new TypeError("Unable to resolve @dcloudio/vite-plugin-uni factory");
}

const uni = resolveUniPluginFactory(require("@dcloudio/vite-plugin-uni"));

export default defineConfig({
  plugins: [uni()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5174,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
