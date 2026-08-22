<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { portalApi } from "@/api/portal";
import type { CourseDetailResponse, LessonSummary } from "@/types/portal";
import { formatCount } from "@/utils/format";

const data = ref<CourseDetailResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");
const courseId = ref(4001);

async function loadData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.course(courseId.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "课程加载失败";
  } finally {
    loading.value = false;
  }
}

function goBack() {
  uni.navigateBack({
    fail: () => uni.reLaunch({ url: "/pages/academy/index" }),
  });
}

function openLesson(lesson: LessonSummary) {
  if (!lesson.is_preview && data.value?.price_label !== "免费" && data.value?.progress === 0) {
    uni.showToast({ title: "请先开通课程学习权限", icon: "none" });
    return;
  }
  uni.showToast({ title: `进入：${lesson.title}`, icon: "none" });
}

function showAction(label: string) {
  uni.showToast({ title: `${label}功能正在接入`, icon: "none" });
}

onLoad((options) => {
  courseId.value = Number(options?.id || 4001);
  void loadData();
});
</script>

<template>
  <view class="course-detail-page">
    <view class="navy-hero course-hero">
      <view class="safe-top" />
      <view class="course-nav-row">
        <view class="course-nav-button back" @tap="goBack"><AppIcon name="arrow" :size="46" /></view>
        <text class="course-nav-title">课程详情</text>
        <view class="course-nav-button" @tap="showAction('分享')"><AppIcon name="share" :size="30" /></view>
      </view>

      <view v-if="data" class="course-hero-copy">
        <view class="course-label-row">
          <view class="pill member">{{ data.level }}</view>
          <view class="pill gold">{{ data.price_label }}</view>
        </view>
        <text class="course-detail-title">{{ data.title }}</text>
        <text class="course-detail-summary">{{ data.summary }}</text>
        <view class="course-detail-meta">
          <text>{{ data.duration_hours }} 小时</text>
          <text>·</text>
          <text>{{ data.lesson_count }} 讲</text>
          <text>·</text>
          <text>{{ formatCount(data.student_count) }} 人学习</text>
        </view>
      </view>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />

    <view v-else-if="data" class="course-body">
      <view class="surface-card progress-card">
        <view class="progress-heading">
          <text>当前学习进度</text>
          <text class="progress-number">{{ data.progress }}%</text>
        </view>
        <view class="progress-track"><view class="progress-value" :style="{ width: `${data.progress}%` }" /></view>
        <text class="progress-caption">学习记录将在 H5、iOS 和 Android 间同步</text>
      </view>

      <view class="detail-section-heading">你将获得</view>
      <view class="highlight-grid">
        <view v-for="item in data.highlights" :key="item" class="highlight-item">
          <view class="highlight-check"><AppIcon name="check" :size="22" /></view>
          <text>{{ item }}</text>
        </view>
      </view>

      <view class="detail-section-heading">课程目录</view>
      <view v-for="chapter in data.chapters" :key="chapter.id" class="surface-card chapter-card">
        <view class="chapter-title-row">
          <text class="chapter-title">{{ chapter.title }}</text>
          <text class="chapter-count">{{ chapter.lessons.length }} 课时</text>
        </view>
        <view
          v-for="lesson in chapter.lessons"
          :key="lesson.id"
          class="lesson-row"
          @tap="openLesson(lesson)"
        >
          <view class="lesson-state" :class="{ learned: lesson.learned }">
            <AppIcon :name="lesson.learned ? 'check' : 'play'" :size="22" />
          </view>
          <view class="lesson-copy">
            <text class="lesson-title">{{ lesson.title }}</text>
            <view class="lesson-meta">
              <text>{{ lesson.duration_minutes }} 分钟</text>
              <text v-if="lesson.is_preview" class="preview-badge">可试看</text>
              <text v-if="lesson.learned" class="learned-label">已学习</text>
            </view>
          </view>
          <AppIcon class="lesson-arrow" name="arrow" :size="38" />
        </view>
      </view>
    </view>

    <view v-if="data" class="course-bottom-bar">
      <view class="course-bottom-info">
        <text class="course-bottom-price">{{ data.price_label }}</text>
        <text class="course-bottom-note">会员权益将由后端统一校验</text>
      </view>
      <button class="course-start-button" @tap="showAction(data.progress ? '继续学习' : '开始学习')">
        <AppIcon name="play" :size="24" />
        {{ data.progress ? '继续学习' : '开始学习' }}
      </button>
    </view>
  </view>
</template>

<style scoped lang="scss">
.course-detail-page {
  min-height: 100vh;
  padding-bottom: calc(142rpx + env(safe-area-inset-bottom));
  background: #f4f6f9;
}

.course-hero {
  padding-bottom: 46rpx;
}

.course-nav-row,
.course-label-row,
.course-detail-meta,
.progress-heading,
.chapter-title-row,
.lesson-row,
.lesson-meta,
.course-bottom-bar,
.course-start-button,
.highlight-item {
  display: flex;
  align-items: center;
}

.course-nav-row,
.progress-heading,
.chapter-title-row {
  justify-content: space-between;
}

.course-nav-row {
  position: relative;
  z-index: 2;
  padding: 24rpx 30rpx 0;
}

.course-nav-button {
  display: flex;
  width: 68rpx;
  height: 68rpx;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.course-nav-button.back {
  transform: rotate(180deg);
}

.course-nav-title {
  color: rgba(255, 255, 255, 0.82);
  font-size: 25rpx;
  font-weight: 800;
}

.course-hero-copy {
  position: relative;
  z-index: 2;
  padding: 38rpx 32rpx 0;
}

.course-label-row {
  gap: 12rpx;
}

.course-detail-title,
.course-detail-summary,
.progress-caption,
.detail-section-heading,
.lesson-title,
.course-bottom-price,
.course-bottom-note {
  display: block;
}

.course-detail-title {
  margin-top: 20rpx;
  font-size: 43rpx;
  font-weight: 900;
  line-height: 1.42;
}

.course-detail-summary {
  margin-top: 16rpx;
  color: rgba(255, 255, 255, 0.72);
  font-size: 24rpx;
  line-height: 1.72;
}

.course-detail-meta {
  margin-top: 24rpx;
  gap: 10rpx;
  color: rgba(255, 255, 255, 0.58);
  font-size: 21rpx;
}

.course-body {
  padding: 24rpx 30rpx 40rpx;
}

.progress-card {
  padding: 26rpx;
}

.progress-heading {
  font-size: 24rpx;
  font-weight: 800;
}

.progress-number {
  color: #f28a1d;
  font-size: 28rpx;
  font-weight: 900;
}

.progress-track {
  height: 12rpx;
  margin-top: 16rpx;
  overflow: hidden;
  border-radius: 8rpx;
  background: #e7ebef;
}

.progress-value {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffad2e, #ff761c);
}

.progress-caption {
  margin-top: 10rpx;
  color: #7b8490;
  font-size: 19rpx;
}

.detail-section-heading {
  margin: 38rpx 2rpx 18rpx;
  color: #161b22;
  font-size: 31rpx;
  font-weight: 900;
}

.highlight-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
}

.highlight-item {
  min-height: 86rpx;
  padding: 16rpx;
  gap: 12rpx;
  border: 1rpx solid #dceaf3;
  border-radius: 18rpx;
  color: #35566e;
  background: #edf6fb;
  font-size: 21rpx;
  font-weight: 700;
  line-height: 1.45;
}

.highlight-check {
  display: flex;
  width: 34rpx;
  height: 34rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #39b995;
}

.chapter-card {
  margin-top: 18rpx;
  padding: 0 24rpx;
  overflow: hidden;
}

.chapter-title-row {
  min-height: 84rpx;
}

.chapter-title {
  font-size: 25rpx;
  font-weight: 900;
}

.chapter-count {
  color: #858e99;
  font-size: 19rpx;
}

.lesson-row {
  min-height: 106rpx;
  gap: 16rpx;
  border-top: 1rpx solid #e6eaee;
}

.lesson-state {
  display: flex;
  width: 46rpx;
  height: 46rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #aab4be;
}

.lesson-state.learned {
  background: #0c6296;
}

.lesson-copy {
  min-width: 0;
  flex: 1;
}

.lesson-title {
  overflow: hidden;
  font-size: 23rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lesson-meta {
  margin-top: 7rpx;
  gap: 10rpx;
  color: #828b96;
  font-size: 18rpx;
}

.preview-badge,
.learned-label {
  padding: 3rpx 8rpx;
  border-radius: 7rpx;
  font-weight: 800;
}

.preview-badge {
  color: #b76713;
  background: #fff0df;
}

.learned-label {
  color: #267b66;
  background: #e4f7f1;
}

.lesson-arrow {
  flex: 0 0 auto;
  color: #a0a8b1;
}

.course-bottom-bar {
  position: fixed;
  z-index: 50;
  right: 0;
  bottom: 0;
  left: 0;
  padding: 16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  gap: 20rpx;
  border-top: 1rpx solid #e4e8ec;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 -12rpx 34rpx rgba(4, 31, 55, 0.08);
  backdrop-filter: blur(16px);
}

.course-bottom-info {
  min-width: 0;
  flex: 1;
}

.course-bottom-price {
  color: #e5821b;
  font-size: 27rpx;
  font-weight: 900;
}

.course-bottom-note {
  margin-top: 4rpx;
  overflow: hidden;
  color: #818a95;
  font-size: 18rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.course-start-button {
  width: 252rpx;
  height: 82rpx;
  flex: 0 0 auto;
  justify-content: center;
  gap: 10rpx;
  border: none;
  border-radius: 44rpx;
  color: #fff;
  background: linear-gradient(135deg, #0d6ca5, #073e69);
  font-size: 25rpx;
  font-weight: 900;
}
</style>
