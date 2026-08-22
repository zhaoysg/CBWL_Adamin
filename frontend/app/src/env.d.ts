/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly MODE: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCK?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
