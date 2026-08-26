import {
  createMockContentDetail,
  createMockCourseDetail,
  mockAcademy,
  mockHome,
  mockMemberCenter,
  mockProfile,
} from "@/mocks/portal";
import { httpRequest } from "@/api/http";
import type {
  AcademyResponse,
  ContentDetailResponse,
  CourseDetailResponse,
  HomeResponse,
  MemberCenterResponse,
  PortalHealth,
  ProfileResponse,
} from "@/types/portal";

const USE_MOCK = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === "true";

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

async function withMockFallback<T>(loader: () => Promise<T>, mockData: T): Promise<T> {
  if (USE_MOCK) return clone(mockData);
  return loader();
}

export const portalApi = {
  health: () => httpRequest<PortalHealth>("/portal/health", { skipAuth: true }),
  home: () => withMockFallback(() => httpRequest<HomeResponse>("/portal/home"), mockHome),
  academy: () =>
    withMockFallback(() => httpRequest<AcademyResponse>("/portal/academy"), mockAcademy),
  profile: () =>
    withMockFallback(() => httpRequest<ProfileResponse>("/portal/profile"), mockProfile),
  content: (id: number) =>
    withMockFallback(
      () => httpRequest<ContentDetailResponse>(`/portal/content/${id}`),
      createMockContentDetail(id),
    ),
  course: (id: number) =>
    withMockFallback(
      () => httpRequest<CourseDetailResponse>(`/portal/course/${id}`),
      createMockCourseDetail(id),
    ),
  memberCenter: () =>
    withMockFallback(
      () => httpRequest<MemberCenterResponse>("/portal/member-center"),
      mockMemberCenter,
    ),
};
