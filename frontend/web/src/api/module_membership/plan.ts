import { request } from "@utils";

const API_PATH = "/membership/plan";

const MemberPlanAPI = {
  list(query: MemberPlanPageQuery) {
    return request<ApiResponse<PageResult<MemberPlanTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  options() {
    return request<ApiResponse<MemberPlanOption[]>>({
      url: `${API_PATH}/options`,
      method: "get",
    });
  },

  detail(id: number) {
    return request<ApiResponse<MemberPlanTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  create(data: MemberPlanForm) {
    return request<ApiResponse<MemberPlanTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data,
    });
  },

  update(id: number, data: MemberPlanForm) {
    return request<ApiResponse<MemberPlanTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data,
    });
  },

  remove(ids: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: ids,
    });
  },

  batchStatus(data: BatchType) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "patch",
      data,
    });
  },
};

export default MemberPlanAPI;

export interface MemberPlanPageQuery extends PageQuery, UserByQueryParams {
  plan_code?: string;
  plan_name?: string;
  rank?: number;
  status?: number;
}

export interface MemberPlanOption {
  id: number;
  plan_code: string;
  plan_name: string;
  rank: number;
}

export interface MemberPlanTable extends BaseType {
  plan_code?: string;
  plan_name?: string;
  rank?: number;
  price?: string | number;
  currency?: "CNY";
  duration_days?: number;
  benefits?: string[];
  status?: number;
  sort_no?: number;
  description?: string;
}

export interface MemberPlanForm extends BaseFormType {
  plan_code: string;
  plan_name: string;
  rank: number;
  price: number;
  currency: "CNY";
  duration_days: number;
  benefits: string[];
  status: number;
  sort_no: number;
  description?: string;
}
