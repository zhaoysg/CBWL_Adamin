const API_BASE = import.meta.env.VITE_APP_BASE_API || "/api/v1";

function request<T>(url: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync("access_token");
    uni.request({
      url: `${API_BASE}${url}`,
      method: "GET",
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (response) => {
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as T);
          return;
        }
        reject(new Error(`请求失败: ${response.statusCode}`));
      },
      fail: reject,
    });
  });
}

export const portalApi = {
  home: () => request<any>("/portal/home"),
  academy: () => request<any>("/portal/academy"),
  profile: () => request<any>("/portal/profile"),
};
