<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { portalApi } from "../../api/portal";
import type { AcademyResponse, CourseCard } from "../../types/portal";
import CwBottomNav from "../../components/portal/CwBottomNav.vue";
import CwIcon from "../../components/portal/CwIcon.vue";
import CwPageState from "../../components/portal/CwPageState.vue";
import { formatCount } from "../../utils/portal-format";

const data = ref<AcademyResponse>();
const loading = ref(true);
const error = ref("");
const activeCategory = ref("全部");

const visibleCourses = computed(() => {
  if (!data.value || activeCategory.value === "全部") return data.value?.courses || [];
  return data.value.courses.filter((course) => course.level === activeCategory.value.replace("新手", ""));
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await portalApi.academy();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "网络连接失败";
  } finally {
    loading.value = false;
  }
}

function openCourse(course: CourseCard) {
  uni.navigateTo({ url: `/pages/course/detail?id=${course.id}` });
}

function openLearning() {
  uni.switchTab({ url: "/pages/mine/index", fail: () => uni.reLaunch({ url: "/pages/mine/index" }) });
}

function reserveLive(title: string) {
  uni.showToast({ title: `已记录预约：${title}`, icon: "none" });
}

onMounted(load);
onShow(() => uni.hideTabBar({ animation: false, fail: () => undefined }));
</script>

<template>
  <view class="academy-page">
    <view class="academy-hero">
      <view class="academy-head">
        <view class="academy-brand">
          <view class="academy-logo">⌂</view>
          <view>
            <view class="academy-title-row">
              <text class="academy-title">投研学院</text>
              <text class="academy-tag">专业投研体系</text>
            </view>
            <text class="academy-subtitle">10 门体系精品课 · 7 大深度专栏 · 专题研讨直播</text>
          </view>
        </view>
        <view class="academy-actions">
          <button class="round-action"><CwIcon name="search" :size="40" tone="white" /></button>
          <button class="learning-button" @tap="openLearning"><CwIcon name="book" :size="27" tone="navy" /><text>我的学习</text></button>
        </view>
      </view>

      <view class="hero-section-title">
        <view class="live-dot" />
        <text>专题直播研讨</text>
        <button class="archive-button"><CwIcon name="live" :size="23" tone="white" /><text>往期回看库（120+期）›</text></button>
      </view>

      <CwPageState v-if="loading || error" :loading="loading" :error="error" dark @retry="load" />
      <scroll-view v-else-if="data" class="live-scroll" scroll-x :show-scrollbar="false">
        <view class="live-list">
          <article v-for="session in data.live_sessions" :key="session.id" class="live-card">
            <view class="live-card__meta">
              <view class="time-badge"><CwIcon name="clock" :size="22" tone="navy" /><text>{{ session.schedule_text }}</text></view>
              <view class="free-badge" :class="{ 'free-badge--member': session.access_label.includes('会员') }">{{ session.access_label }}</view>
            </view>
            <text class="live-card__title">{{ session.title }}</text>
            <text class="live-card__subtitle">{{ session.subtitle }}</text>
            <view class="tag-row"><text v-for="tag in session.tags" :key="tag" class="topic-tag">#{{ tag }}</text></view>
            <view class="live-card__footer">
              <text>{{ formatCount(session.reservation_count) }} 人已预约</text>
              <button class="reserve-button" @tap="reserveLive(session.title)"><CwIcon name="bell" :size="21" tone="orange" /><text>预约直播</text></button>
            </view>
          </article>
        </view>
      </scroll-view>
    </view>

    <view v-if="data" class="academy-content">
      <section class="content-section">
        <view class="section-heading">
          <view class="section-title"><view class="section-bar" /><text>星球深度图文专栏</text></view>
          <text class="section-link">全 {{ data.columns.length + 5 }} 专栏 ›</text>
        </view>
        <scroll-view class="column-scroll" scroll-x :show-scrollbar="false">
          <view class="column-list">
            <article v-for="column in data.columns" :key="column.id" class="column-card" :class="`column-card--${column.accent}`">
              <view class="column-card__top">
                <text class="column-status"><CwIcon name="check" :size="19" tone="green" />{{ column.status }}</text>
                <text class="column-access"><CwIcon name="crown" :size="22" tone="gold" />{{ column.access_label }}</text>
              </view>
              <text class="column-title">{{ column.title }}</text>
              <text class="column-summary">{{ column.summary }}</text>
              <view class="column-footer"><text>▤ 已更新 {{ column.article_count }} 篇深度长文</text><text class="start-link">开始阅读 ›</text></view>
            </article>
          </view>
        </scroll-view>
      </section>

      <section class="content-section course-section">
        <view class="section-heading">
          <view class="section-title"><view class="section-bar" /><text>体系化精品课</text></view>
          <text class="section-count">共 10 门精选课程</text>
        </view>

        <scroll-view class="course-filter-scroll" scroll-x :show-scrollbar="false">
          <view class="course-filter-list">
            <button
              v-for="category in data.course_categories"
              :key="category"
              class="course-filter"
              :class="{ 'course-filter--active': activeCategory === category }"
              @tap="activeCategory = category"
            >{{ category === '全部' ? '✦ 全部' : category }}</button>
          </view>
        </scroll-view>

        <view class="course-list">
          <article v-for="course in visibleCourses" :key="course.id" class="course-card" @tap="openCourse(course)">
            <view class="course-topline">
              <view class="course-kind-icon"><CwIcon name="book" :size="30" tone="green" /></view>
              <text class="level-badge">{{ course.level }}</text>
              <text class="course-duration">{{ course.duration_hours }}小时 · {{ course.lesson_count }}讲</text>
              <text v-if="course.badge" class="hot-badge">● {{ course.badge }}</text>
            </view>
            <text class="course-title">{{ course.title }}</text>
            <text class="course-summary">{{ course.summary }}</text>
            <view class="course-tags"><text v-for="tag in course.tags" :key="tag">{{ tag }}</text></view>
            <view class="course-footer">
              <text class="course-price">{{ course.price_label }}</text>
              <view v-if="course.progress" class="mini-progress"><view class="mini-progress__bar" :style="{ width: `${course.progress}%` }" /></view>
              <text class="course-action">进入课程 ›</text>
            </view>
          </article>
          <view v-if="!visibleCourses.length" class="empty-course">该分类课程正在筹备中</view>
        </view>
      </section>
    </view>

    <CwBottomNav active="academy" />
  </view>
</template>

<style scoped lang="scss">
.academy-page { min-height: 100vh; padding-bottom: 170rpx; background: #f5f7fa; }
.academy-hero {
  padding: calc(var(--status-bar-height) + 34rpx) 0 45rpx;
  color: #ffffff;
  overflow: hidden;
  background:
    radial-gradient(circle at 95% 5%, rgba(42, 93, 139, 0.34), transparent 34%),
    linear-gradient(145deg, #031a34, #06294b 62%, #0b3c66);
}
.academy-head { display: flex; align-items: center; justify-content: space-between; gap: 18rpx; padding: 0 30rpx; }
.academy-brand { display: flex; align-items: center; gap: 16rpx; min-width: 0; }
.academy-logo { display: flex; align-items: center; justify-content: center; width: 74rpx; height: 74rpx; color: #ffa32a; font-size: 40rpx; font-weight: 900; border: 2rpx solid rgba(255, 157, 39, 0.65); border-radius: 19rpx; }
.academy-title-row { display: flex; align-items: center; gap: 12rpx; }
.academy-title { font-size: 38rpx; font-weight: 900; }
.academy-tag { padding: 5rpx 9rpx; color: #f3a638; font-size: 17rpx; font-weight: 800; background: rgba(255, 156, 31, 0.12); border-radius: 5rpx; }
.academy-subtitle { display: block; max-width: 420rpx; margin-top: 7rpx; overflow: hidden; color: rgba(255,255,255,.68); font-size: 21rpx; white-space: nowrap; text-overflow: ellipsis; }
.academy-actions { display: flex; align-items: center; gap: 12rpx; }
.round-action { display: flex; align-items: center; justify-content: center; width: 70rpx; height: 70rpx; margin: 0; padding: 0; background: rgba(255,255,255,.08); border: 1rpx solid rgba(255,255,255,.14); border-radius: 50%; }
.round-action::after, .learning-button::after, .archive-button::after, .reserve-button::after, .course-filter::after { border: 0; }
.learning-button { display: flex; align-items: center; gap: 8rpx; margin: 0; padding: 18rpx 20rpx; color: #102942; font-size: 21rpx; font-weight: 900; line-height: 1; background: linear-gradient(105deg,#ffdc48,#ff9a1c); border: 0; border-radius: 34rpx; }
.hero-section-title { display: flex; align-items: center; gap: 13rpx; margin: 38rpx 30rpx 22rpx; font-size: 30rpx; font-weight: 900; }
.live-dot { width: 13rpx; height: 13rpx; background: #ff4f55; border: 4rpx solid rgba(255,255,255,.14); border-radius: 50%; }
.archive-button { display: flex; align-items: center; gap: 8rpx; margin: 0 0 0 auto; padding: 10rpx 16rpx; color: rgba(255,255,255,.82); font-size: 19rpx; line-height: 1; background: rgba(255,255,255,.08); border: 1rpx solid rgba(255,255,255,.14); border-radius: 25rpx; }
.live-scroll { width: 100%; white-space: nowrap; }
.live-list { display: inline-flex; gap: 20rpx; padding: 0 30rpx 8rpx; }
.live-card { display: flex; flex-direction: column; width: 500rpx; min-height: 290rpx; padding: 26rpx; color: #151b22; white-space: normal; background: #ffffff; border-radius: 24rpx; box-shadow: 0 14rpx 32rpx rgba(0,0,0,.14); box-sizing: border-box; }
.live-card__meta, .column-card__top, .course-topline, .course-footer, .live-card__footer { display: flex; align-items: center; }
.live-card__meta { justify-content: space-between; gap: 12rpx; }
.time-badge, .free-badge { display: inline-flex; align-items: center; gap: 5rpx; padding: 7rpx 11rpx; color: #315575; font-size: 19rpx; font-weight: 700; background: #edf4f9; border-radius: 7rpx; }
.free-badge { color: #259078; background: #e7faf4; }
.free-badge--member { color: #aa7621; background: #fff3da; }
.live-card__title { display: block; margin-top: 20rpx; font-size: 31rpx; font-weight: 900; line-height: 1.45; }
.live-card__subtitle { display: -webkit-box; margin-top: 10rpx; overflow: hidden; color: #7d858f; font-size: 22rpx; line-height: 1.55; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.tag-row { display: flex; flex-wrap: wrap; gap: 9rpx; margin-top: 16rpx; }
.topic-tag { padding: 5rpx 10rpx; color: #315575; font-size: 18rpx; background: #f1f5f8; border-radius: 5rpx; }
.live-card__footer { justify-content: space-between; gap: 12rpx; margin-top: auto; padding-top: 18rpx; color: #858c95; font-size: 21rpx; border-top: 1rpx solid #e7eaed; }
.reserve-button { display: flex; align-items: center; gap: 6rpx; margin: 0; padding: 10rpx 15rpx; color: #a66a1e; font-size: 20rpx; font-weight: 800; line-height: 1; background: #fff3e4; border: 0; border-radius: 24rpx; }
.academy-content { background: #f5f7fa; }
.content-section { padding: 40rpx 0 10rpx; }
.section-heading { display: flex; align-items: center; justify-content: space-between; padding: 0 30rpx; }
.section-title { display: flex; align-items: center; gap: 14rpx; color: #141b22; font-size: 32rpx; font-weight: 900; }
.section-bar { width: 6rpx; height: 42rpx; background: #0b4e82; border-radius: 5rpx; }
.section-link { color: #234f72; font-size: 22rpx; font-weight: 700; }
.section-count { color: #8a929b; font-size: 21rpx; }
.column-scroll { width: 100%; margin-top: 24rpx; white-space: nowrap; }
.column-list { display: inline-flex; gap: 20rpx; padding: 0 30rpx 12rpx; }
.column-card { position: relative; display: flex; flex-direction: column; width: 520rpx; min-height: 285rpx; padding: 25rpx 25rpx 22rpx 31rpx; overflow: hidden; white-space: normal; background: #ffffff; border: 1rpx solid #e6e9ed; border-radius: 22rpx; box-shadow: 0 10rpx 24rpx rgba(8,39,70,.06); box-sizing: border-box; }
.column-card::before { position: absolute; top: 0; bottom: 0; left: 0; width: 6rpx; content: ""; background: #19b7ce; }
.column-card--orange::before { background: #ff9d2f; }
.column-card__top { justify-content: space-between; gap: 10rpx; }
.column-status, .column-access { display: inline-flex; align-items: center; gap: 5rpx; color: #25967e; font-size: 19rpx; font-weight: 700; }
.column-access { color: #9b721f; }
.column-title { display: block; margin-top: 19rpx; color: #131a21; font-size: 32rpx; font-weight: 900; }
.column-summary { display: -webkit-box; margin-top: 10rpx; overflow: hidden; color: #737c87; font-size: 23rpx; line-height: 1.65; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.column-footer { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; margin-top: auto; padding-top: 18rpx; color: #7e8791; font-size: 20rpx; border-top: 1rpx solid #eceef0; }
.start-link { color: #174a75; font-weight: 900; }
.course-section { padding-bottom: 20rpx; }
.course-filter-scroll { width: 100%; margin-top: 24rpx; white-space: nowrap; }
.course-filter-list { display: inline-flex; gap: 12rpx; padding: 0 30rpx 10rpx; }
.course-filter { flex: 0 0 auto; margin: 0; padding: 14rpx 21rpx; color: #26313b; font-size: 21rpx; font-weight: 700; line-height: 1; background: #ffffff; border: 1rpx solid #e4e7ea; border-radius: 29rpx; }
.course-filter--active { color: #ffffff; background: #082f57; border-color: #082f57; }
.course-list { padding: 12rpx 30rpx 20rpx; }
.course-card { margin-bottom: 22rpx; padding: 27rpx 27rpx 24rpx; background: #ffffff; border: 1rpx solid #e5e8ec; border-radius: 24rpx; box-shadow: 0 12rpx 28rpx rgba(8,39,70,.055); }
.course-topline { gap: 10rpx; }
.course-kind-icon { display: flex; align-items: center; justify-content: center; width: 45rpx; height: 45rpx; background: #e9faf4; border-radius: 12rpx; }
.level-badge { padding: 5rpx 10rpx; color: #27886f; font-size: 18rpx; background: #e7f9f2; border-radius: 5rpx; }
.course-duration { color: #7d858e; font-size: 21rpx; }
.hot-badge { margin-left: auto; padding: 5rpx 10rpx; color: #ffffff; font-size: 18rpx; font-weight: 800; background: #ef6509; border-radius: 5rpx; }
.course-title { display: block; margin-top: 20rpx; color: #111820; font-size: 34rpx; font-weight: 900; }
.course-summary { display: block; margin-top: 11rpx; color: #7c848d; font-size: 24rpx; line-height: 1.65; }
.course-tags { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 20rpx; }
.course-tags text { padding: 7rpx 12rpx; color: #315575; font-size: 19rpx; background: #f1f5f8; border-radius: 6rpx; }
.course-footer { gap: 14rpx; margin-top: 22rpx; padding-top: 18rpx; border-top: 1rpx solid #eceef1; }
.course-price { color: #33b991; font-size: 26rpx; font-weight: 900; }
.course-action { margin-left: auto; color: #164b77; font-size: 22rpx; font-weight: 900; }
.mini-progress { width: 130rpx; height: 7rpx; overflow: hidden; background: #edf0f2; border-radius: 7rpx; }
.mini-progress__bar { height: 100%; background: linear-gradient(90deg,#ffad29,#ff711c); border-radius: inherit; }
.empty-course { padding: 60rpx; color: #87919c; text-align: center; background: #ffffff; border-radius: 22rpx; }
</style>
