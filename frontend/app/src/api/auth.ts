import { httpRequest } from "@/api/http";
import { clearSession, getAccessToken, saveSession } from "@/utils/auth";

export interface CaptchaResponse {
  enable: boolean;
  key: string;
  img_base: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_info: Record<string, unknown>;
}

export interface LoginForm {
  username: string;
  password: string;
  captchaKey?: string;
}

export const authApi = {
  captcha: () => httpRequest<CaptchaResponse>("/system/auth/captcha/get", { skipAuth: true }),

  completeSlider: (captchaKey: string) =>
    httpRequest<{ captcha_key: string; verified: boolean }>(
      "/system/auth/captcha/slider/complete",
      {
        method: "POST",
        data: { captcha_key: captchaKey },
        skipAuth: true,
      },
    ),

  async login(form: LoginForm): Promise<LoginResponse> {
    const result = await httpRequest<LoginResponse>("/system/auth/login", {
      method: "POST",
      data: {
        username: form.username,
        password: form.password,
        captcha_key: form.captchaKey || "",
        captcha: "",
        login_type: "移动端",
      },
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      skipAuth: true,
    });
    saveSession({
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
      tokenType: result.token_type,
      expiresIn: result.expires_in,
      userInfo: result.user_info,
    });
    return result;
  },

  async logout(): Promise<void> {
    const token = getAccessToken();
    try {
      if (token) {
        await httpRequest<void>("/system/auth/logout", {
          method: "POST",
          data: token,
          headers: { "Content-Type": "application/json" },
          skipRefresh: true,
        });
      }
    } finally {
      clearSession();
    }
  },
};
