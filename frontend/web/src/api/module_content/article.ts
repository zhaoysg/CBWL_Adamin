import { request } from "@utils";

const API_PATH = "/content/article";

const ContentArticleAPI = {
  list(query: ContentPageQuery) {
    return request<ApiResponse<PageResult<ContentTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detail(id: number) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  create(data: ContentCreateForm) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/create`,
      method: "post",
      data,
    });
  },

  update(id: number, data: ContentUpdateForm) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/update/${id}`,
      method: "patch",
      data,
    });
  },

  publish(id: number, data: ContentPublishForm) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/publish/${id}`,
      method: "post",
      data,
    });
  },

  offline(id: number, versionNo: number) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/offline/${id}`,
      method: "post",
      data: { version_no: versionNo },
    });
  },

  archive(id: number, versionNo: number) {
    return request<ApiResponse<ContentDetail>>({
      url: `${API_PATH}/archive/${id}`,
      method: "post",
      data: { version_no: versionNo },
    });
  },

  remove(ids: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: { ids },
    });
  },
};

export default ContentArticleAPI;

export type ContentType = "article" | "research" | "trade" | "institution" | "macro" | "notice";
export type ContentAccessLevel = "public" | "login" | "member" | "premium";
export type ContentStatus = 0 | 1 | 2 | 3;

export interface ContentPageQuery extends PageQuery, UserByQueryParams {
  category_id?: number;
  content_type?: ContentType;
  title?: string;
  slug?: string;
  author_name?: string;
  access_level?: ContentAccessLevel;
  status?: ContentStatus;
  is_pinned?: boolean;
  is_featured?: boolean;
  published_at?: string[];
}

export interface ContentTable extends BaseType {
  category_id?: number;
  category_name?: string;
  content_type?: ContentType;
  title?: string;
  slug?: string;
  summary?: string;
  cover_url?: string;
  author_name?: string;
  access_level?: ContentAccessLevel;
  plan_ids?: number[];
  status?: ContentStatus;
  published_at?: string;
  offline_at?: string;
  is_pinned?: boolean;
  is_featured?: boolean;
  sort_no?: number;
  version_no?: number;
  like_count?: number;
  comment_count?: number;
  description?: string;
}

export interface ContentDetail extends ContentTable {
  body?: string;
  body_format?: "html";
}

export interface ContentCreateForm {
  category_id: number;
  content_type: ContentType;
  title: string;
  slug: string;
  summary?: string;
  cover_url?: string;
  body: string;
  body_format: "html";
  author_name: string;
  access_level: ContentAccessLevel;
  plan_ids: number[];
  is_pinned: boolean;
  is_featured: boolean;
  sort_no: number;
  description?: string;
}

export interface ContentUpdateForm extends Partial<ContentCreateForm> {
  version_no: number;
}

export interface ContentPublishForm {
  version_no: number;
  published_at?: string;
}
