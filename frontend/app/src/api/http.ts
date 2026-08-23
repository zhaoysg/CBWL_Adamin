import { clearSession, getAccessToken, getRefreshToken, updateTokens } from "@/utils/auth";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
const TIMEOUT = 15_000;

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface ApiEnvelope<T> {
  code?: number;
  message?: string;
  msg?: string;
  data?: T;
  success?: boolean;
}

interface RequestOptions {
  method?: HttpMethod;
  data?: unknown;
  headers?: Record<string, string>;
  skipAuth?: boolean;
  skipRefresh?: boolean;
}

interface RefreshPayload {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly code?: number,
    public readonly data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function unwrap<T>(payload: T | ApiEnvelope<T>): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    const envelope = payload as ApiEnvelope<T>;
    if (envelope.success === false || (envelope.code !== undefined && ![0, 200, 201].includes(envelope.code))) {
      throw new ApiError(envelope.message || envelope.msg || "接口返回异常", 400, envelope.code, envelope.data);
    }
    if (envelope.data !== undefined) return envelope.data;
  }
  return payload as T;
}

function rawRequest<T>(
  path: string,
  options: RequestOptions,
): Promise<{ statusCode: number; data: T | ApiEnvelope<T> }> {
  return new Promise((resolve, reject) => {
    const token = options.skipAuth ? "" : getAccessToken();
    uni.request({
      url: `${API_BASE}${path}`,
      method: options.method || "GET",
      data: options.data,
      timeout: TIMEOUT,
      header: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
      success: (response: UniApp.RequestSuccessCallbackResult) => {
        resolve({
          statusCode: response.statusCode || 0,
          data: response.data as T | ApiEnvelope<T>,
        });
      },
      fail: (error: UniApp.GeneralCallbackResult) => {
        reject(new ApiError(error.errMsg || "网络连接失败", 0));
      },
    });
  });
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  refreshPromise = (async () => {
    try {
      const response = await rawRequest<RefreshPayload>("/system/auth/token/refresh", {
        method: "POST",
        data: refreshToken,
        headers: { "Content-Type": "application/json" },
        skipAuth: true,
        skipRefresh: true,
      });
      if (response.statusCode < 200 || response.statusCode >= 300) return false;
      const payload = unwrap(response.data);
      updateTokens(payload.access_token, payload.refresh_token, payload.expires_in);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function httpRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await rawRequest<T>(path, options);
  if (response.statusCode === 401 && !options.skipRefresh && !options.skipAuth) {
    if (await refreshSession()) {
      return httpRequest<T>(path, { ...options, skipRefresh: true });
    }
    clearSession();
  }

  if (response.statusCode < 200 || response.statusCode >= 300) {
    const envelope = response.data as ApiEnvelope<T>;
    throw new ApiError(
      envelope.msg || envelope.message || `服务请求失败（${response.statusCode || "网络异常"}）`,
      response.statusCode,
      envelope.code,
      envelope.data,
    );
  }
  return unwrap(response.data);
}
