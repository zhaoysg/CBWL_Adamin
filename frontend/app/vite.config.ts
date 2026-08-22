import { createRequire } from "node:module";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv, type PluginOption } from "vite";

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

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const useMock = env.VITE_USE_MOCK === "true";
  const apiBase = (env.VITE_API_BASE_URL || "").trim();
  const platform = process.env.UNI_PLATFORM || "h5";

  if (mode === "production" && useMock) {
    throw new Error("生产构建禁止 VITE_USE_MOCK=true");
  }
  if (mode === "production" && platform.startsWith("app") && !/^https:\/\//i.test(apiBase)) {
    throw new Error("APP 生产构建必须配置 HTTPS 绝对 API 地址");
  }

  return {
    plugins: [uni()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    build: {
      sourcemap: false,
      target: "es2018",
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
  };
});
