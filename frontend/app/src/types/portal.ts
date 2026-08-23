export type AccessLevel = "public" | "login" | "member" | "premium";
export type LockReason = "login_required" | "membership_required" | "plan_required";

export interface Author {
  id: number;
  name: string;
  title: string;
  avatar_text: string;
}

export type PinnedTargetType = "content" | "academy" | "member";

export interface PinnedItem {
  id: number;
  title: string;
  subtitle: string;
  icon: string;
  accent: "orange" | "blue" | "cyan" | string;
  target_type: PinnedTargetType;
  target_id?: number | null;
}

export interface CommentPreview {
  author: string;
  avatar_text: string;
  content: string;
}

export interface FeedItem {
  id: number;
  category: string;
  content_type: string;
  title: string;
  summary: string;
  cover_url?: string | null;
  published_at: string;
  access_level: AccessLevel;
  can_access: boolean;
  lock_reason?: LockReason | null;
  like_count: number;
  comment_count: number;
  author: Author;
  liked_by_names: string[];
  comments: CommentPreview[];
}

export interface MemberSummary {
  id: number;
  nickname: string;
  level_name: string;
  expire_date?: string | null;
  member_no: string;
  joined_days: number;
  slogan: string;
  is_member: boolean;
  active_plan_codes: string[];
}

export interface HomeResponse {
  brand_name: string;
  brand_slogan: string;
  joined_count: number;
  member?: MemberSummary | null;
  pinned: PinnedItem[];
  categories: string[];
  feed: FeedItem[];
}

export interface LiveSession {
  id: number;
  schedule_text: string;
  title: string;
  subtitle: string;
  access_label: string;
  tags: string[];
  reservation_count: number;
}

export interface ColumnCard {
  id: number;
  status: string;
  title: string;
  summary: string;
  article_count: number;
  access_label: string;
  accent: string;
}

export interface CourseCard {
  id: number;
  category: string;
  level: string;
  duration_hours: number;
  lesson_count: number;
  title: string;
  summary: string;
  tags: string[];
  price_label: string;
  badge?: string | null;
  progress: number;
}

export interface AcademyResponse {
  live_sessions: LiveSession[];
  columns: ColumnCard[];
  course_categories: string[];
  courses: CourseCard[];
}

export interface LearningStats {
  learning_courses: number;
  reading_columns: number;
  replay_count: number;
  learning_hours: number;
}

export interface RecentLearning {
  course_id: number;
  category: string;
  title: string;
  lesson_title: string;
  learned_lessons: number;
  total_lessons: number;
  progress: number;
  last_studied_at: string;
}

export interface Achievement {
  code: string;
  name: string;
  icon: string;
  unlocked: boolean;
}

export interface AssetEntry {
  title: string;
  meta: string;
  badge?: string | null;
  icon: string;
}

export interface ProfileResponse {
  member: MemberSummary;
  benefits: string[];
  stats: LearningStats;
  recent_learning?: RecentLearning | null;
  achievements: Achievement[];
  assets: AssetEntry[];
}

export interface ContentSection {
  heading?: string | null;
  paragraphs: string[];
}

export interface ContentDetailResponse {
  id: number;
  category: string;
  title: string;
  summary: string;
  cover_url?: string | null;
  published_at: string;
  access_level: AccessLevel;
  can_access: boolean;
  like_count: number;
  comment_count: number;
  reading_minutes: number;
  author: Author;
  body_html?: string | null;
  sections: ContentSection[];
}

export interface LessonSummary {
  id: number;
  title: string;
  duration_minutes: number;
  is_preview: boolean;
  learned: boolean;
}

export interface CourseChapter {
  id: number;
  title: string;
  lessons: LessonSummary[];
}

export interface CourseDetailResponse {
  id: number;
  category: string;
  level: string;
  duration_hours: number;
  lesson_count: number;
  title: string;
  summary: string;
  price_label: string;
  progress: number;
  student_count: number;
  highlights: string[];
  chapters: CourseChapter[];
}

export interface MemberPlan {
  id: number;
  code: string;
  name: string;
  rank: number;
  duration_days: number;
  period_label: string;
  price: string;
  original_price?: string | null;
  benefits: string[];
  recommended: boolean;
}

export interface MemberCenterResponse {
  member?: MemberSummary | null;
  current_benefits: string[];
  plans: MemberPlan[];
}

export interface PortalHealth {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  data_source: "demo" | "database";
  production_ready: boolean;
  reason?: string | null;
}
