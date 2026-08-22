<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import BottomNav from "@/components/BottomNav.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { portalApi } from "@/api/portal";
import type { FeedItem, HomeResponse, PinnedItem } from "@/types/portal";
import { formatCount, formatRelativeTime } from "@/utils/format";

const data = ref<HomeResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");
const activeCategory = ref("全部");

const filteredFeed = computed(() => {
  if (!data.value || activeCategory.value === "全部") return data.value?.feed || [];
  return data.value.feed.filter((item) => item.category.includes(activeCategory.value));
});

const pinIconMap: Record<string, string> = {
  guide: "guide",
  compass: "compass",
  chip: "chip",
};

async function loadData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.home();
    if (!data.value.categories.includes(activeCategory.value)) activeCategory.value = "全部";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "未知错误";
  } finally {
    loading.value = false;
  }
}

function selectCategory(category: string) {
  activeCategory.value = category;
}

function openPinned(item: PinnedItem) {
  uni.showToast({ title: item.title, icon: "none" });
}

function openFeed(item: FeedItem) {
  uni.showToast({ title: `打开：${item.title}`, icon: "none" });
}

function showComingSoon(label: string) {
  uni.showToast({ title: `${label}功能正在接入`, icon: "none" });
}

onMounted(loadData);
</script>

<template>
  <view class="page-shell home-page">
    <view v-if="data" class="navy-hero home-hero">
      <view class="safe-top" />
      <view class="hero-content">
        <view class="brand-line">
          <view class="brand-group">
            <view class="brand-logo">财</view>
            <view class="brand-copy">
              <view class="brand-title-row">
                <text class="brand-title">{{ data.brand_name }}</text>
                <view class="verified">✓</view>
              </view>
              <text class="brand-subtitle">{{ data.brand_slogan }}</text>
            </view>
          </view>
          <view class="hero-actions">
            <view class="glass-icon-button" @tap="showComingSoon('搜索')">
              <AppIcon name="search" :size="42" />
            </view>
            <view class="glass-icon-button notification" @tap="showComingSoon('通知')">
              <AppIcon name="bell" :size="24" />
              <view class="notice-dot" />
            </view>
          </view>
        </view>

        <view class="join-line">
          <view class="joined-members">
            <view class="avatar-stack">
              <view class="mini-avatar avatar-a">若</view>
              <view class="mini-avatar avatar-b">志</view>
              <view class="mini-avatar avatar-c">马</view>
              <view class="mini-avatar avatar-more">＋</view>
            </view>
            <text class="joined-text">{{ formatCount(data.joined_count) }} 位专业投资人已加入</text>
          </view>
          <button class="gold-button join-button" @tap="showComingSoon('会员开通')">
            <AppIcon name="crown" :size="30" />
            立即加入
          </button>
        </view>
      </view>
    </view>

    <view v-if="data" class="home-content">
      <view class="surface-card pinned-panel">
        <view
          v-for="(item, index) in data.pinned"
          :key="item.id"
          class="pinned-row"
          :class="{ 'with-divider': index > 0 }"
          @tap="openPinned(item)"
        >
          <view class="pin-icon" :class="`accent-${item.accent}`">
            <AppIcon :name="pinIconMap[item.icon] || 'book'" :size="34" />
          </view>
          <view class="pin-copy">
            <view class="pin-title-line">
              <text class="pin-label" :class="`accent-${item.accent}`">📌 置顶</text>
              <text class="pin-title">{{ item.title }}</text>
            </view>
            <text class="pin-subtitle">{{ item.subtitle }}</text>
          </view>
          <AppIcon class="pin-arrow" name="arrow" :size="42" />
        </view>
      </view>

      <scroll-view scroll-x class="category-scroll" :show-scrollbar="false">
        <view class="category-row">
          <view
            v-for="category in data.categories"
            :key="category"
            class="category-pill"
            :class="{ active: activeCategory === category }"
            @tap="selectCategory(category)"
          >
            {{ category }}
          </view>
          <view class="category-pill category-menu" @tap="showComingSoon('更多分类')">
            <AppIcon name="menu" :size="34" />
          </view>
        </view>
      </scroll-view>

      <view class="feed-list">
        <view
          v-for="item in filteredFeed"
          :key="item.id"
          class="surface-card feed-card"
          @tap="openFeed(item)"
        >
          <view class="feed-accent" />
          <view class="feed-main">
            <view class="feed-meta-row">
              <view class="feed-meta-left">
                <text class="feed-category">#{{ item.category }}</text>
                <text class="feed-time">{{ formatRelativeTime(item.published_at) }}</text>
              </view>
              <view v-if="item.access_level !== 'public'" class="pill member">
                <AppIcon name="lock" :size="20" />
                仅限会员
              </view>
              <view v-else class="pill">公开内容</view>
            </view>

            <text class="feed-title">{{ item.title }}</text>
            <text class="feed-summary">{{ item.summary }}</text>

            <view class="feed-footer">
              <view class="feed-stats">
                <view class="stat-item"><AppIcon name="like" :size="34" />{{ item.like_count }}</view>
                <view class="stat-item"><AppIcon name="comment" :size="31" />{{ item.comment_count }}</view>
              </view>
              <view class="author-badge">
                <text class="author-icon">{{ item.author.avatar_text }}</text>
                <text>{{ item.author.title }}：{{ item.author.name }}</text>
              </view>
            </view>

            <view v-if="item.liked_by_names.length || item.comments.length" class="discussion-box">
              <view v-if="item.liked_by_names.length" class="liked-row">
                <text class="liked-icon">♨</text>
                <text>
                  {{ item.liked_by_names.join('、') }} 等 {{ item.like_count }} 人赞过
                </text>
              </view>
              <view v-for="comment in item.comments" :key="`${item.id}-${comment.author}`" class="comment-row">
                <view class="comment-avatar">{{ comment.avatar_text }}</view>
                <text class="comment-text"><text class="comment-author">{{ comment.author }}：</text>{{ comment.content }}</text>
              </view>
              <text v-if="item.comments.length" class="all-comments">查看全部 {{ item.comment_count }} 条讨论 ›</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />
    <BottomNav active="home" />
  </view>
</template>

<style scoped lang="scss">
.home-hero {
  min-height: 510rpx;
  padding-bottom: 138rpx;
}

.hero-content {
  position: relative;
  z-index: 2;
  padding: 38rpx 30rpx 24rpx;
}

.brand-line,
.join-line,
.brand-group,
.brand-title-row,
.hero-actions,
.joined-members,
.feed-meta-row,
.feed-meta-left,
.feed-footer,
.feed-stats,
.stat-item,
.author-badge,
.liked-row,
.comment-row,
.pin-title-line {
  display: flex;
  align-items: center;
}

.brand-line,
.join-line,
.feed-meta-row,
.feed-footer {
  justify-content: space-between;
}

.brand-line {
  gap: 20rpx;
}

.brand-group {
  min-width: 0;
  flex: 1;
  gap: 18rpx;
}

.brand-logo {
  display: flex;
  width: 82rpx;
  height: 82rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2rpx solid rgba(255, 174, 51, 0.65);
  border-radius: 22rpx;
  color: #ffe96f;
  background: rgba(4, 20, 39, 0.5);
  box-shadow: inset 0 0 0 1rpx rgba(255, 255, 255, 0.08);
  font-size: 42rpx;
  font-weight: 900;
}

.brand-copy {
  min-width: 0;
}

.brand-title-row {
  gap: 10rpx;
}

.brand-title {
  font-size: 38rpx;
  font-weight: 900;
  letter-spacing: 1rpx;
}

.verified {
  display: flex;
  width: 28rpx;
  height: 28rpx;
  align-items: center;
  justify-content: center;
  border-radius: 8rpx;
  color: #442800;
  background: #ff9225;
  font-size: 18rpx;
  font-weight: 900;
}

.brand-subtitle {
  display: block;
  max-width: 450rpx;
  margin-top: 8rpx;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.76);
  font-size: 23rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-actions {
  flex: 0 0 auto;
  gap: 12rpx;
}

.notification {
  position: relative;
}

.notice-dot {
  position: absolute;
  top: 8rpx;
  right: 8rpx;
  width: 14rpx;
  height: 14rpx;
  border: 3rpx solid #0a3158;
  border-radius: 50%;
  background: #ff3e4d;
}

.join-line {
  margin-top: 34rpx;
  gap: 16rpx;
}

.joined-members {
  min-width: 0;
  flex: 1;
}

.avatar-stack {
  display: flex;
  flex: 0 0 auto;
  padding-left: 8rpx;
}

.mini-avatar {
  display: flex;
  width: 52rpx;
  height: 52rpx;
  margin-left: -10rpx;
  align-items: center;
  justify-content: center;
  border: 3rpx solid #fff;
  border-radius: 50%;
  color: #fff;
  font-size: 21rpx;
  font-weight: 800;
}

.avatar-a { background: #40b6d1; }
.avatar-b { background: #f4a51e; }
.avatar-c { background: #6a43c9; }
.avatar-more { background: #092846; }

.joined-text {
  min-width: 0;
  margin-left: 14rpx;
  overflow: hidden;
  font-size: 24rpx;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.join-button {
  flex: 0 0 auto;
}

.home-content {
  position: relative;
  z-index: 4;
  margin-top: -152rpx;
  padding-bottom: 40rpx;
}

.pinned-panel {
  margin: 0 30rpx;
  padding: 6rpx 26rpx;
}

.pinned-row {
  display: flex;
  min-height: 112rpx;
  align-items: center;
  gap: 18rpx;
}

.pinned-row.with-divider {
  border-top: 1rpx solid #e5e9ee;
}

.pin-icon {
  display: flex;
  width: 58rpx;
  height: 58rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
}

.accent-orange { color: #f18b27; background: #fff2e7; }
.accent-blue { color: #0c4a80; background: #e8f1f8; }
.accent-cyan { color: #1688ae; background: #e5f7fb; }

.pin-copy {
  min-width: 0;
  flex: 1;
}

.pin-title-line {
  min-width: 0;
  gap: 12rpx;
}

.pin-label {
  flex: 0 0 auto;
  padding: 3rpx 8rpx;
  border-radius: 7rpx;
  font-size: 18rpx;
  font-weight: 800;
}

.pin-title {
  min-width: 0;
  overflow: hidden;
  font-size: 26rpx;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pin-subtitle {
  display: block;
  margin-top: 6rpx;
  overflow: hidden;
  color: #808894;
  font-size: 22rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pin-arrow {
  flex: 0 0 auto;
  color: #929aa5;
}

.category-scroll {
  margin-top: 42rpx;
}

.category-row {
  display: inline-flex;
  padding: 0 30rpx 10rpx;
  gap: 14rpx;
}

.category-pill {
  display: flex;
  height: 58rpx;
  padding: 0 28rpx;
  align-items: center;
  justify-content: center;
  border: 1rpx solid #e1e6eb;
  border-radius: 12rpx;
  color: #161a20;
  background: #fff;
  box-shadow: 0 8rpx 20rpx rgba(15, 34, 52, 0.04);
  font-size: 25rpx;
  font-weight: 700;
  white-space: nowrap;
}

.category-pill.active {
  border-color: #052f58;
  color: #fff;
  background: #052f58;
}

.category-menu {
  width: 60rpx;
  padding: 0;
}

.feed-list {
  padding: 8rpx 30rpx 20rpx;
}

.feed-card {
  position: relative;
  margin-top: 24rpx;
  overflow: hidden;
}

.feed-accent {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 7rpx;
  background: #07548e;
}

.feed-main {
  padding: 30rpx 28rpx 28rpx 34rpx;
}

.feed-meta-row {
  gap: 16rpx;
}

.feed-meta-left {
  min-width: 0;
  gap: 14rpx;
}

.feed-category {
  color: #f28e24;
  font-size: 23rpx;
  font-weight: 900;
}

.feed-time {
  color: #777f89;
  font-size: 22rpx;
}

.feed-title,
.feed-summary {
  display: block;
}

.feed-title {
  margin-top: 22rpx;
  color: #15191f;
  font-size: 32rpx;
  font-weight: 900;
  line-height: 1.55;
}

.feed-summary {
  display: -webkit-box;
  margin-top: 12rpx;
  overflow: hidden;
  color: #7b838e;
  font-size: 24rpx;
  line-height: 1.75;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.feed-footer {
  margin-top: 24rpx;
  gap: 18rpx;
}

.feed-stats {
  gap: 26rpx;
}

.stat-item {
  gap: 7rpx;
  color: #6e7680;
  font-size: 23rpx;
}

.author-badge {
  min-width: 0;
  padding: 7rpx 12rpx;
  gap: 8rpx;
  border-radius: 10rpx;
  color: #315878;
  background: #f3f6f9;
  font-size: 20rpx;
  font-weight: 700;
}

.author-icon {
  display: flex;
  width: 27rpx;
  height: 27rpx;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #315878;
  font-size: 16rpx;
}

.discussion-box {
  margin-top: 18rpx;
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  background: #f5f6f8;
}

.liked-row {
  gap: 10rpx;
  padding-bottom: 14rpx;
  border-bottom: 1rpx solid #dce1e6;
  color: #31516d;
  font-size: 21rpx;
  font-weight: 700;
  line-height: 1.5;
}

.liked-icon {
  color: #ed8e25;
}

.comment-row {
  margin-top: 14rpx;
  align-items: flex-start;
  gap: 12rpx;
}

.comment-avatar {
  display: flex;
  width: 32rpx;
  height: 32rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #33a0c8;
  font-size: 16rpx;
  font-weight: 800;
}

.comment-text {
  color: #293542;
  font-size: 21rpx;
  line-height: 1.65;
}

.comment-author {
  color: #183d5d;
  font-weight: 900;
}

.all-comments {
  display: block;
  margin-top: 14rpx;
  color: #0a416e;
  font-size: 21rpx;
  font-weight: 800;
}
</style>
