import { request } from "@utils";

const API_PATH = "/content/category";

const ContentCategoryAPI = {
  list(query: ContentCategoryPageQuery) {
    return request<ApiResponse<PageResult<ContentCategoryTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  tree(enabledOnly = false) {
    return request<ApiResponse<ContentCategoryTree[]>>({
      url: `${API_PATH}/tree`,
      method: "get",
      params: { enabled_only: enabledOnly },
    });
  },

  options() {
    return request<ApiResponse<ContentCategoryOption[]>>({
      url: `${API_PATH}/options`,
      method: "get",
    });
  },

  detail(id: number) {
    return request<ApiResponse<ContentCategoryTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  create(data: ContentCategoryForm) {
    return request<ApiResponse<ContentCategoryTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data,
    });
  },

  update(id: number, data: ContentCategoryForm) {
    return request<ApiResponse<ContentCategoryTable>>({
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

export default ContentCategoryAPI;

export interface ContentCategoryPageQuery extends PageQuery, UserByQueryParams {
  parent_id?: number;
  category_code?: string;
  category_name?: string;
  status?: number;
}

export interface ContentCategoryOption {
  id: number;
  parent_id?: number;
  category_code: string;
  category_name: string;
  status: number;
}

export interface ContentCategoryTree extends ContentCategoryOption {
  icon?: string;
  sort_no: number;
  children: ContentCategoryTree[];
}

export interface ContentCategoryTable extends BaseType {
  parent_id?: number;
  category_code?: string;
  category_name?: string;
  icon?: string;
  status?: number;
  sort_no?: number;
  description?: string;
}

export interface ContentCategoryForm extends BaseFormType {
  parent_id?: number;
  category_code: string;
  category_name: string;
  icon?: string;
  status: number;
  sort_no: number;
  description?: string;
}
