<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import BottomNav from "@/components/BottomNav.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { portalApi } from "@/api/portal";
import type { AcademyResponse, CourseCard } from "@/types/portal";
import { formatCount } from "@/utils/format";

const data = ref<AcademyResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");
const activeCategory = ref("全部");

const filteredCourses = computed(() => {
  if (!data.value || activeCategory.value === "全部") return data.value?.courses || [];
  return data.value.courses.filter((course) => course.level.includes(activeCategory.value.replace("新手", "入门")));
});

async function loadData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.academy();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "未知错误";
  } finally {
    loading.value = false;
  }
}

function openAction(label: string) {
  uni.showToast({ title: `${label}功能正在接入`, icon: "none" });
}

function openCourse(course: CourseCard) {
  uni.showToast({ title: `打开课程：${course.title}`, icon: "none" });
}

onMounted(loadData);
</script>

<template>
  <view class="page-shell academy-page">
    <view v-if="data" class="navy-hero academy-hero">
      <view class="safe-top" />
      <view class="academy-header">
        <view class="academy-brand">
          <view class="academy-logo"><AppIcon name="academy" :size="50" /></view>
          <view class="academy-copy">
            <view class="academy-title-line">
              <text class="academy-title">投研学院</text>
              <text class="academy-kicker">专业投研体系</text>
            </view>
            <text class="academy-subtitle">10 门体系精品课 · 7 大深度专栏 · 专题研讨直播</text>
          </view>
        </view>
        <view class="academy-actions">
          <view class="glass-icon-button" @tap="openAction('学院搜索')">
            <AppIcon name="search" :size="42" />
          </view>
          <button class="gold-button learning-button" @tap="openAction('我的学习')">
            <AppIcon name="book" :size="26" />
            我的学习
          </button>
        </view>
      </view>

      <view class="live-heading-row">
        <view class="live-heading"><text class="live-dot" />专题直播研讨</view>
        <view class="replay-entry" @tap="openAction('往期回看')">
          <AppIcon name="play" :size="22" />
          往期回看库（120+期）
          <AppIcon name="arrow" :size="28" />
        </view>
      </view>

      <scroll-view scroll-x class="live-scroll" :show-scrollbar="false">
        <view class="live-card-row">
          <view v-for="session in data.live_sessions" :key="session.id" class="live-card">
            <view class="live-meta">
              <view class="pill"><AppIcon name="clock" :size="20" />{{ session.schedule_text }}</view>
              <view class="pill member" :class="{ orange: session.access_label.includes('会员') }">
                {{ session.access_label }}
              </view>
            </view>
            <text class="live-title">{{ session.title }}</text>
            <text class="live-subtitle">{{ session.subtitle }}</text>
            <view class="tag-row">
              <text v-for="tag in session.tags" :key="tag" class="topic-tag">#{{ tag }}</text>
            </view>
            <view class="live-footer">
              <text class="reservation-count">{{ formatCount(session.reservation_count) }} 人已预约</text>
              <button class="reserve-button" @tap.stop="openAction('直播预约')">♧ 预约直播</button>
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <view v-if="data" class="academy-body">
      <view class="section-title-row section-padding">
        <text class="section-title">星球深度图文专栏</text>
        <text class="section-link" @tap="openAction('全部专栏')">全 7 专栏 ›</text>
      </view>

      <scroll-view scroll-x class="column-scroll" :show-scrollbar="false">
        <view class="column-row">
          <view
            v-for="column in data.columns"
            :key="column.id"
            class="surface-card column-card"
            :class="`column-${column.accent}`"
            @tap="openAction(column.title)"
          >
            <view class="column-top">
              <view class="column-status"><AppIcon name="check" :size="19" />{{ column.status }}</view>
              <view class="column-access"><AppIcon name="crown" :size="22" />{{ column.access_label }}</view>
            </view>
            <text class="column-title">{{ column.title }}</text>
            <text class="column-summary">{{ column.summary }}</text>
            <view class="column-footer">
              <text><AppIcon name="note" :size="22" /> 已更新 {{ column.article_count }} 篇深度长文</text>
              <text class="column-action">开始阅读 ›</text>
            </view>
          </view>
        </view>
      </scroll-view>

      <view class="section-title-row course-heading section-padding">
        <text class="section-title">体系化精品课</text>
        <text class="course-count">共 10 门精选课程</text>
      </view>

      <scroll-view scroll-x class="course-tab-scroll" :show-scrollbar="false">
        <view class="course-tabs">
          <view
            v-for="category in data.course_categories"
            :key="category"
            class="course-tab"
            :class="{ active: activeCategory === category }"
            @tap="activeCategory = category"
          >
            <text v-if="category === '全部'">✦</text>
            <text v-else-if="category === '新手入门'">★</text>
            <text v-else>⌁</text>
            {{ category }}
          </view>
        </view>
      </scroll-view>

      <view class="course-list">
        <view
          v-for="course in filteredCourses"
          :key="course.id"
          class="surface-card course-card"
          @tap="openCourse(course)"
        >
          <view class="course-accent" />
          <view class="course-main">
            <view class="course-meta-row">
              <view class="course-meta-left">
                <view class="course-icon">＄</view>
                <view class="pill member">{{ course.level }}</view>
                <text class="course-duration">{{ course.duration_hours }}小时 · {{ course.lesson_count }}讲</text>
              </view>
              <view v-if="course.badge" class="hot-badge">♨ {{ course.badge }}</view>
            </view>
            <text class="course-title">{{ course.title }}</text>
            <text class="course-summary">{{ course.summary }}</text>
            <view class="course-tags">
              <text v-for="tag in course.tags" :key="tag" class="course-tag">{{ tag }}</text>
            </view>
            <view class="course-footer">
              <text class="course-price">{{ course.price_label }}</text>
              <text class="course-cta">立即实战 ›</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />
    <BottomNav active="academy" />
  </view>
</template>

<style scoped lang="scss">
.academy-hero {
  padding-bottom: 48rpx;
}

.academy-header,
.academy-brand,
.academy-title-line,
.academy-actions,
.live-heading-row,
.live-heading,
.replay-entry,
.live-meta,
.live-footer,
.column-top,
.column-footer,
.course-meta-row,
.course-meta-left,
.course-footer {
  display: flex;
  align-items: center;
}

.academy-header,
.live-heading-row,
.live-meta,
.live-footer,
.column-top,
.column-footer,
.course-meta-row,
.course-footer {
  justify-content: space-between;
}

.academy-header {
  position: relative;
  z-index: 2;
  padding: 32rpx 30rpx 0;
  gap: 20rpx;
}

.academy-brand {
  min-width: 0;
  flex: 1;
  gap: 18rpx;
}

.academy-logo {
  display: flex;
  width: 78rpx;
  height: 78rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2rpx solid rgba(255, 159, 45, 0.7);
  border-radius: 20rpx;
  color: #ffa333;
  background: rgba(4, 20, 39, 0.48);
}

.academy-copy {
  min-width: 0;
}

.academy-title-line {
  gap: 12rpx;
}

.academy-title {
  font-size: 36rpx;
  font-weight: 900;
}

.academy-kicker {
  padding: 5rpx 10rpx;
  border-radius: 8rpx;
  color: #ff9b29;
  background: rgba(255, 148, 29, 0.12);
  font-size: 18rpx;
  font-weight: 800;
}

.academy-subtitle {
  display: block;
  max-width: 390rpx;
  margin-top: 8rpx;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.78);
  font-size: 22rpx;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.academy-actions {
  flex: 0 0 auto;
  gap: 12rpx;
}

.learning-button {
  height: 66rpx;
  padding: 0 22rpx;
  font-size: 23rpx;
}

.live-heading-row {
  position: relative;
  z-index: 2;
  margin-top: 42rpx;
  padding: 0 30rpx;
  gap: 16rpx;
}

.live-heading {
  gap: 12rpx;
  font-size: 30rpx;
  font-weight: 900;
}

.live-dot {
  width: 13rpx;
  height: 13rpx;
  border: 3rpx solid rgba(255, 255, 255, 0.55);
  border-radius: 50%;
  background: #ff5159;
}

.replay-entry {
  height: 50rpx;
  padding: 0 16rpx;
  gap: 8rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.22);
  border-radius: 28rpx;
  color: rgba(255, 255, 255, 0.86);
  background: rgba(255, 255, 255, 0.1);
  font-size: 20rpx;
  font-weight: 700;
}

.live-scroll {
  position: relative;
  z-index: 2;
  margin-top: 24rpx;
}

.live-card-row {
  display: inline-flex;
  padding: 0 30rpx 12rpx;
  gap: 20rpx;
}

.live-card {
  display: inline-flex;
  width: 530rpx;
  min-height: 336rpx;
  padding: 26rpx;
  flex-direction: column;
  border-radius: 26rpx;
  color: #151a22;
  background: #fff;
  box-shadow: 0 14rpx 34rpx rgba(1, 14, 31, 0.2);
  white-space: normal;
}

.live-title,
.live-subtitle,
.column-title,
.column-summary,
.course-title,
.course-summary {
  display: block;
}

.live-title {
  margin-top: 20rpx;
  font-size: 31rpx;
  font-weight: 900;
  line-height: 1.45;
}

.live-subtitle {
  margin-top: 10rpx;
  color: #7b838d;
  font-size: 22rpx;
  line-height: 1.6;
}

.tag-row {
  display: flex;
  margin-top: 20rpx;
  flex-wrap: wrap;
  gap: 10rpx;
}

.topic-tag {
  color: #315876;
  background: #f2f6f9;
  font-size: 20rpx;
}

.live-footer {
  margin-top: auto;
  padding-top: 18rpx;
  border-top: 1rpx solid #e6e9ed;
}

.reservation-count {
  color: #737c88;
  font-size: 22rpx;
}

.reserve-button {
  height: 56rpx;
  padding: 0 18rpx;
  border: none;
  border-radius: 30rpx;
  color: #a25d10;
  background: #fff0df;
  font-size: 22rpx;
  font-weight: 800;
}

.academy-body {
  padding-bottom: 38rpx;
}

.section-padding {
  padding: 38rpx 30rpx 18rpx;
}

.column-row {
  display: inline-flex;
  padding: 0 30rpx 16rpx;
  gap: 20rpx;
}

.column-card {
  position: relative;
  display: inline-flex;
  width: 530rpx;
  min-height: 300rpx;
  padding: 26rpx 26rpx 24rpx 34rpx;
  flex-direction: column;
  overflow: hidden;
  white-space: normal;

  &::before {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 8rpx;
    content: "";
  }
}

.column-cyan::before { background: #2cc5d5; }
.column-orange::before { background: #ff9b32; }

.column-status {
  display: flex;
  align-items: center;
  gap: 7rpx;
  color: #31a987;
  font-size: 20rpx;
  font-weight: 800;
}

.column-orange .column-status { color: #ed8c2b; }

.column-access {
  display: flex;
  align-items: center;
  gap: 6rpx;
  color: #8c5b12;
  font-size: 19rpx;
  font-weight: 800;
}

.column-title {
  margin-top: 24rpx;
  font-size: 31rpx;
  font-weight: 900;
}

.column-summary {
  margin-top: 10rpx;
  color: #747d88;
  font-size: 23rpx;
  line-height: 1.65;
}

.column-footer {
  margin-top: auto;
  padding-top: 22rpx;
  color: #78818d;
  font-size: 20rpx;
}

.column-action {
  color: #073b68;
  font-weight: 900;
}

.course-heading {
  padding-bottom: 16rpx;
}

.course-count {
  color: #878f99;
  font-size: 22rpx;
}

.course-tabs {
  display: inline-flex;
  padding: 0 30rpx 12rpx;
  gap: 12rpx;
}

.course-tab {
  display: flex;
  height: 54rpx;
  padding: 0 22rpx;
  align-items: center;
  gap: 8rpx;
  border: 1rpx solid #e1e6eb;
  border-radius: 30rpx;
  color: #252a31;
  background: #fff;
  font-size: 22rpx;
  font-weight: 700;
  white-space: nowrap;
}

.course-tab.active {
  border-color: #052f58;
  color: #fff;
  background: #052f58;
}

.course-list {
  padding: 4rpx 30rpx 24rpx;
}

.course-card {
  position: relative;
  margin-top: 20rpx;
  overflow: hidden;
}

.course-accent {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 7rpx;
  background: #3bd3ab;
}

.course-main {
  padding: 28rpx 28rpx 26rpx 34rpx;
}

.course-meta-row {
  gap: 16rpx;
}

.course-meta-left {
  min-width: 0;
  gap: 10rpx;
}

.course-icon {
  display: flex;
  width: 44rpx;
  height: 44rpx;
  align-items: center;
  justify-content: center;
  border-radius: 14rpx;
  color: #fff;
  background: #38c49c;
  font-size: 23rpx;
  font-weight: 900;
}

.course-duration {
  color: #7d858f;
  font-size: 21rpx;
  white-space: nowrap;
}

.hot-badge {
  flex: 0 0 auto;
  padding: 5rpx 12rpx;
  border-radius: 8rpx;
  color: #fff;
  background: #ed6908;
  font-size: 19rpx;
  font-weight: 800;
}

.course-title {
  margin-top: 26rpx;
  font-size: 32rpx;
  font-weight: 900;
}

.course-summary {
  margin-top: 10rpx;
  color: #7a828d;
  font-size: 23rpx;
  line-height: 1.65;
}

.course-tags {
  display: flex;
  margin-top: 22rpx;
  flex-wrap: wrap;
  gap: 10rpx;
}

.course-tag {
  padding: 6rpx 12rpx;
  border-radius: 7rpx;
  color: #315a78;
  background: #f0f5f8;
  font-size: 19rpx;
}

.course-footer {
  margin-top: 22rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid #e5e9ed;
}

.course-price {
  color: #42bd98;
  font-size: 25rpx;
  font-weight: 900;
}

.course-cta {
  color: #073a65;
  font-size: 22rpx;
  font-weight: 900;
}
</style>
