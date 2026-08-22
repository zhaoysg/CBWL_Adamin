import { mockAcademy, mockHome, mockProfile } from "@/mocks/portal";
import type {
  AcademyResponse,
  HomeResponse,
  PortalHealth,
  ProfileResponse,
} from "@/types/portal";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const TIMEOUT = 15_000;

interface ApiEnvelope<T> {
  code?: number;
  message?: string;
  msg?: string;
  data?: T;
}

function unwrap<T>(payload: T | ApiEnvelope<T>): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    const envelope = payload as ApiEnvelope<T>;
    if (envelope.code !== undefined && ![0, 200].includes(envelope.code)) {
      throw new Error(envelope.message || envelope.msg || "接口返回异常");
    }
    if (envelope.data !== undefined) return envelope.data;
  }
  return payload as T;
}

function request<T>(path: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync("access_token");
    uni.request<T | ApiEnvelope<T>>({
      url: `${API_BASE}${path}`,
      method: "GET",
      timeout: TIMEOUT,
      header: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (response) => {
        const statusCode = response.statusCode || 0;
        if (statusCode === 401) {
          uni.removeStorageSync("access_token");
          reject(new Error("登录状态已失效，请重新登录"));
          return;
        }
        if (statusCode < 200 || statusCode >= 300) {
          reject(new Error(`服务请求失败（${statusCode || "网络异常"}）`));
          return;
        }
        try {
          resolve(unwrap(response.data));
        } catch (error) {
          reject(error);
        }
      },
      fail: (error) => reject(new Error(error.errMsg || "网络连接失败")),
    });
  });
}

async function withMockFallback<T>(loader: () => Promise<T>, mockData: T): Promise<T> {
  if (USE_MOCK) return JSON.parse(JSON.stringify(mockData)) as T;
  return loader();
}

export const portalApi = {
  health: () => request<PortalHealth>("/portal/health"),
  home: () => withMockFallback(() => request<HomeResponse>("/portal/home"), mockHome),
  academy: () =>
    withMockFallback(() => request<AcademyResponse>("/portal/academy"), mockAcademy),
  profile: () =>
    withMockFallback(() => request<ProfileResponse>("/portal/profile"), mockProfile),
};
