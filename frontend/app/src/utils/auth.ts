export interface StoredSession {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  userInfo: Record<string, unknown>;
}

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const TOKEN_TYPE_KEY = "token_type";
const TOKEN_EXPIRES_AT_KEY = "token_expires_at";
const USER_INFO_KEY = "user_info";

export function getAccessToken(): string {
  return String(uni.getStorageSync(ACCESS_TOKEN_KEY) || "");
}

export function getRefreshToken(): string {
  return String(uni.getStorageSync(REFRESH_TOKEN_KEY) || "");
}

export function hasSession(): boolean {
  return Boolean(getAccessToken());
}

export function saveSession(session: StoredSession): void {
  uni.setStorageSync(ACCESS_TOKEN_KEY, session.accessToken);
  uni.setStorageSync(REFRESH_TOKEN_KEY, session.refreshToken);
  uni.setStorageSync(TOKEN_TYPE_KEY, session.tokenType || "Bearer");
  uni.setStorageSync(TOKEN_EXPIRES_AT_KEY, Date.now() + session.expiresIn * 1000);
  uni.setStorageSync(USER_INFO_KEY, session.userInfo);
}

export function updateTokens(accessToken: string, refreshToken: string, expiresIn: number): void {
  uni.setStorageSync(ACCESS_TOKEN_KEY, accessToken);
  uni.setStorageSync(REFRESH_TOKEN_KEY, refreshToken);
  uni.setStorageSync(TOKEN_EXPIRES_AT_KEY, Date.now() + expiresIn * 1000);
}

export function clearSession(): void {
  for (const key of [
    ACCESS_TOKEN_KEY,
    REFRESH_TOKEN_KEY,
    TOKEN_TYPE_KEY,
    TOKEN_EXPIRES_AT_KEY,
    USER_INFO_KEY,
  ]) {
    uni.removeStorageSync(key);
  }
}

export function loginUrl(redirect?: string): string {
  const value = redirect?.startsWith("/") ? redirect : "/pages/mine/index";
  return `/pages/auth/login?redirect=${encodeURIComponent(value)}`;
}
