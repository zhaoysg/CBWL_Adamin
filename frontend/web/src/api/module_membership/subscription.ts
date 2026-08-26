import { request } from "@utils";

const API_PATH = "/membership/subscription";

const MemberSubscriptionAPI = {
  list(query: MemberSubscriptionPageQuery) {
    return request<ApiResponse<PageResult<MemberSubscriptionTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detail(id: number) {
    return request<ApiResponse<MemberSubscriptionTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  userOptions(keyword?: string) {
    return request<ApiResponse<MemberSubscriptionUserOption[]>>({
      url: `${API_PATH}/user-options`,
      method: "get",
      params: { keyword, limit: 20 },
    });
  },

  grantManual(data: MemberSubscriptionGrantForm) {
    return request<ApiResponse<MemberSubscriptionTable>>({
      url: `${API_PATH}/grant/manual`,
      method: "post",
      data,
    });
  },

  revoke(id: number, data: MemberSubscriptionRevokeForm) {
    return request<ApiResponse<MemberSubscriptionTable>>({
      url: `${API_PATH}/revoke/${id}`,
      method: "post",
      data,
    });
  },
};

export default MemberSubscriptionAPI;

export type SubscriptionSource = "manual" | "payment" | "migration" | "promotion";
export type SubscriptionEffectiveStatus = "upcoming" | "active" | "expired" | "revoked";

export interface MemberSubscriptionPageQuery extends PageQuery, UserByQueryParams {
  keyword?: string;
  user_id?: number;
  plan_id?: number;
  source?: SubscriptionSource;
  source_ref?: string;
  status?: number;
  effective_status?: SubscriptionEffectiveStatus;
  starts_at?: string[];
  expires_at?: string[];
}

export interface MemberSubscriptionUserOption {
  id: number;
  username: string;
  name: string;
  mobile?: string | null;
}

export interface MemberSubscriptionTable extends BaseType {
  user_id: number;
  username: string;
  user_name: string;
  mobile?: string | null;
  plan_id: number;
  plan_code: string;
  plan_name: string;
  rank: number;
  source: SubscriptionSource;
  source_ref: string;
  status: number;
  effective_status: SubscriptionEffectiveStatus;
  starts_at: string;
  expires_at: string;
  revoked_at?: string | null;
  grant_reason: string;
  revoke_reason?: string | null;
  version_no: number;
  description?: string | null;
}

export interface MemberSubscriptionGrantForm {
  user_id: number;
  plan_id: number;
  source_ref: string;
  starts_at?: string;
  expires_at?: string;
  grant_reason: string;
  description?: string;
}

export interface MemberSubscriptionRevokeForm {
  version_no: number;
  reason: string;
}
