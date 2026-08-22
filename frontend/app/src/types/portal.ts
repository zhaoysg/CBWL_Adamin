export type AccessLevel = "public" | "login" | "member" | "premium";

export interface Author {
  id: number;
  name: string;
  title: string;
  avatar_text: string;
}

export interface PinnedItem {
  id: number;
  title: string;
  subtitle: string;
  icon: string;
  accent: "orange" | "blue" | "cyan" | string;
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
  published_at: string;
  access_level: AccessLevel;
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
  expire_date: string;
  member_no: string;
  joined_days: number;
  slogan: string;
}

export interface HomeResponse {
  brand_name: string;
  brand_slogan: string;
  joined_count: number;
  member: MemberSummary;
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
  recent_learning: RecentLearning;
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
  published_at: string;
  access_level: AccessLevel;
  like_count: number;
  comment_count: number;
  reading_minutes: number;
  author: Author;
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
  code: string;
  name: string;
  period_label: string;
  price: number;
  original_price?: number | null;
  benefits: string[];
  recommended: boolean;
}

export interface MemberCenterResponse {
  member: MemberSummary;
  current_benefits: string[];
  plans: MemberPlan[];
}

export interface PortalHealth {
  status: "ok";
  service: string;
  version: string;
}
