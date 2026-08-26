<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { portalApi } from "../../api/portal";
import type { FeedItem, HomeResponse, PinnedItem } from "../../types/portal";
import CwBottomNav from "../../components/portal/CwBottomNav.vue";
import CwIcon from "../../components/portal/CwIcon.vue";
import CwPageState from "../../components/portal/CwPageState.vue";
import { accessLabel, formatCount, relativeTime } from "../../utils/portal-format";
import { loginUrl } from "../../utils/auth";

const data = ref<HomeResponse>();
const loading = ref(true);
const error = ref("");
const activeCategory = ref("全部");

const categories = computed(() => [
  "全部",
  ...new Set((data.value?.categories || []).filter((item) => item && item !== "全部")),
]);

const visibleFeed = computed(() => {
  if (!data.value || activeCategory.value === "全部") return data.value?.feed || [];
  return data.value.feed.filter((item) => item.category === activeCategory.value);
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await portalApi.home();
    if (!categories.value.includes(activeCategory.value)) activeCategory.value = "全部";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "网络连接失败";
  } finally {
    loading.value = false;
  }
}

function joinMember() {
  uni.navigateTo({ url: "/pages/member/index" });
}

function openPinned(item: PinnedItem) {
  if (item.target_type === "academy") {
    uni.switchTab({ url: "/pages/academy/index", fail: () => uni.reLaunch({ url: "/pages/academy/index" }) });
    return;
  }
  if (item.target_type === "member") {
    joinMember();
    return;
  }
  if (item.target_id) uni.navigateTo({ url: `/pages/content/detail?id=${item.target_id}` });
}

function openContent(item: FeedItem) {
  const target = `/pages/content/detail?id=${item.id}`;
  if (item.can_access) {
    uni.navigateTo({ url: target });
    return;
  }
  if (item.lock_reason === "login_required") {
    uni.navigateTo({ url: loginUrl(target) });
    return;
  }
  uni.navigateTo({ url: "/pages/member/index" });
}

function openSearch() {
  uni.showToast({ title: "搜索功能将在内容检索模块开放", icon: "none" });
}

onShow(() => {
  uni.hideTabBar({ animation: false, fail: () => undefined });
  void load();
});
</script>

<template>
  <view class="home-page">
    <view class="hero">
      <view class="hero__top">
        <view class="brand-group">
          <view class="brand-logo">财</view>
          <view class="brand-copy">
            <view class="brand-title-row">
              <text class="brand-title">{{ data?.brand_name || "财不外露" }}</text>
              <text class="verified">✓</text>
            </view>
            <text class="brand-slogan">{{ data?.brand_slogan || "学术财富与智慧的聚集地 · 私享投研智库" }}</text>
          </view>
        </view>
        <view class="hero-actions">
          <button class="round-action" aria-label="搜索" @tap="openSearch">
            <CwIcon name="search" :size="42" tone="white" />
          </button>
          <button class="round-action round-action--dot" aria-label="通知">
            <CwIcon name="bell" :size="30" tone="white" />
          </button>
        </view>
      </view>

      <view class="community-row">
        <view class="avatar-stack">
          <view v-for="(label, index) in ['若', '志', '马', '+']" :key="label" class="mini-avatar" :class="`mini-avatar--${index}`">{{ label }}</view>
        </view>
        <text class="community-count">{{ formatCount(data?.joined_count || 0) }} 位专业投资人已加入</text>
        <button class="join-button" @tap="joinMember">
          <CwIcon name="crown" :size="30" tone="navy" />
          <text>{{ data?.member?.is_member ? "会员中心" : "立即加入" }}</text>
        </button>
      </view>
    </view>

    <view class="content-shell">
      <CwPageState v-if="loading || error" :loading="loading" :error="error" @retry="load" />

      <template v-else-if="data">
        <view class="pinned-panel">
          <button v-for="item in data.pinned" :key="item.id" class="pinned-item" hover-class="pinned-item--hover" @tap="openPinned(item)">
            <view class="pinned-icon" :class="`pinned-icon--${item.accent}`">
              <CwIcon :name="item.icon" :size="34" :tone="item.accent === 'orange' ? 'orange' : item.accent === 'cyan' ? 'cyan' : 'navy'" />
            </view>
            <view class="pinned-copy">
              <view class="pinned-title-line">
                <text class="pin-label">置顶</text>
                <text class="pinned-title">{{ item.title }}</text>
              </view>
              <text class="pinned-subtitle">{{ item.subtitle }}</text>
            </view>
            <CwIcon name="arrow" :size="45" tone="muted" />
          </button>
        </view>

        <scroll-view class="category-scroll" scroll-x :show-scrollbar="false">
          <view class="category-list">
            <button
              v-for="category in categories"
              :key="category"
              class="category-chip"
              :class="{ 'category-chip--active': activeCategory === category }"
              @tap="activeCategory = category"
            >{{ category }}</button>
            <button class="category-chip category-chip--menu"><CwIcon name="menu" :size="30" tone="muted" /></button>
          </view>
        </scroll-view>

        <view class="feed-list">
          <article v-for="item in visibleFeed" :key="item.id" class="feed-card" @tap="openContent(item)">
            <view class="feed-accent" />
            <view class="feed-head">
              <view class="feed-meta">
                <text class="feed-category">#{{ item.category }}</text>
                <text class="feed-time">{{ relativeTime(item.published_at) }}</text>
              </view>
              <view v-if="item.access_level !== 'public'" class="access-badge">
                <CwIcon name="lock" :size="22" tone="green" />
                <text>{{ accessLabel(item.access_level) }}</text>
              </view>
            </view>

            <text class="feed-title">{{ item.title }}</text>
            <text class="feed-summary">{{ item.summary }}</text>

            <view class="engagement-row">
              <view class="engagement-item"><CwIcon name="like" :size="32" tone="muted" /><text>{{ item.like_count }}</text></view>
              <view class="engagement-item"><CwIcon name="comment" :size="30" tone="muted" /><text>{{ item.comment_count }}</text></view>
              <view class="author-badge"><text>{{ item.author.title }} · {{ item.author.name }}</text></view>
            </view>

            <view v-if="item.liked_by_names.length || item.comments.length" class="discussion-box" @tap.stop="openContent(item)">
              <view v-if="item.liked_by_names.length" class="liked-line">
                <CwIcon name="like" :size="26" tone="orange" />
                <text>{{ item.liked_by_names.join('、') }} 等 {{ item.like_count }} 人赞过</text>
              </view>
              <view v-for="comment in item.comments.slice(0, 2)" :key="`${item.id}-${comment.author}`" class="comment-line">
                <view class="comment-avatar">{{ comment.avatar_text }}</view>
                <text><text class="comment-author">{{ comment.author }}：</text>{{ comment.content }}</text>
              </view>
              <text v-if="item.comment_count" class="discussion-more">查看全部 {{ item.comment_count }} 条讨论 ›</text>
            </view>
          </article>

          <view v-if="!visibleFeed.length" class="empty-card">该分类暂时没有内容</view>
        </view>
      </template>
    </view>

    <CwBottomNav active="home" />
  </view>
</template>

<style scoped lang="scss">
.home-page {
  min-height: 100vh;
  padding-bottom: 170rpx;
  background: #f5f7fa;
}
.hero {
  position: relative;
  z-index: 1;
  padding: calc(var(--status-bar-height) + 36rpx) 30rpx 170rpx;
  color: #ffffff;
  overflow: hidden;
  background:
    radial-gradient(circle at 90% 20%, rgba(31, 89, 139, 0.42), transparent 36%),
    linear-gradient(145deg, #031a34 0%, #062747 58%, #0c3c67 100%);
}
.hero::after {
  position: absolute;
  top: 15rpx;
  right: -70rpx;
  width: 260rpx;
  height: 270rpx;
  content: "财";
  color: rgba(255, 255, 255, 0.025);
  font-size: 250rpx;
  font-weight: 900;
  line-height: 1;
}
.hero__top,
.community-row,
.brand-group,
.brand-title-row,
.hero-actions,
.engagement-row,
.feed-head,
.feed-meta,
.liked-line {
  display: flex;
  align-items: center;
}
.hero__top { position: relative; z-index: 1; justify-content: space-between; gap: 22rpx; }
.brand-group { min-width: 0; gap: 18rpx; }
.brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 78rpx;
  height: 78rpx;
  color: #fff3a5;
  font-size: 42rpx;
  font-weight: 900;
  background: linear-gradient(145deg, rgba(255, 181, 57, 0.18), rgba(4, 26, 53, 0.72));
  border: 2rpx solid rgba(255, 176, 54, 0.68);
  border-radius: 22rpx;
  box-shadow: inset 0 0 24rpx rgba(255, 188, 59, 0.08);
}
.brand-copy { min-width: 0; }
.brand-title-row { gap: 10rpx; }
.brand-title { font-size: 38rpx; font-weight: 900; letter-spacing: 1rpx; }
.verified {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 29rpx;
  height: 29rpx;
  color: #ffffff;
  font-size: 19rpx;
  font-weight: 900;
  background: #ff8b23;
  border-radius: 50%;
}
.brand-slogan {
  display: block;
  max-width: 440rpx;
  margin-top: 8rpx;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.72);
  font-size: 21rpx;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.hero-actions { gap: 12rpx; }
.round-action {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 76rpx;
  height: 76rpx;
  margin: 0;
  padding: 0;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.14);
  border-radius: 50%;
  box-shadow: inset 0 0 24rpx rgba(255, 255, 255, 0.04);
}
.round-action::after { border: 0; }
.round-action--dot::before {
  position: absolute;
  top: 7rpx;
  right: 7rpx;
  width: 14rpx;
  height: 14rpx;
  content: "";
  background: #ff4457;
  border: 3rpx solid #0a3157;
  border-radius: 50%;
}
.community-row { position: relative; z-index: 1; gap: 14rpx; margin-top: 34rpx; }
.avatar-stack { display: flex; align-items: center; padding-left: 8rpx; }
.mini-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 53rpx;
  height: 53rpx;
  margin-left: -10rpx;
  color: #ffffff;
  font-size: 23rpx;
  font-weight: 800;
  background: #27a6c3;
  border: 3rpx solid #ffffff;
  border-radius: 50%;
}
.mini-avatar--1 { background: #f3a51f; }
.mini-avatar--2 { background: #7446c5; }
.mini-avatar--3 { color: #ffc048; background: #092d53; }
.community-count { flex: 1; min-width: 0; font-size: 25rpx; font-weight: 600; }
.join-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  min-width: 174rpx;
  margin: 0;
  padding: 19rpx 22rpx;
  color: #122437;
  font-size: 25rpx;
  font-weight: 900;
  line-height: 1;
  background: linear-gradient(105deg, #ffd93c, #ff9417);
  border: 0;
  border-radius: 38rpx;
  box-shadow: 0 12rpx 30rpx rgba(255, 156, 24, 0.24);
}
.join-button::after { border: 0; }
.content-shell { position: relative; z-index: 2; margin-top: -137rpx; }
.pinned-panel {
  margin: 0 28rpx;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 28rpx;
  box-shadow: 0 20rpx 50rpx rgba(9, 38, 69, 0.16);
}
.pinned-item {
  display: flex;
  align-items: center;
  gap: 18rpx;
  width: 100%;
  min-height: 118rpx;
  margin: 0;
  padding: 20rpx 24rpx;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 0;
}
.pinned-item + .pinned-item { border-top: 1rpx solid #e7e9ec; }
.pinned-item::after { border: 0; }
.pinned-item--hover { background: #f8fafc; }
.pinned-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 62rpx;
  height: 62rpx;
  background: #edf5fb;
  border-radius: 16rpx;
}
.pinned-icon--orange { background: #fff4e8; }
.pinned-icon--cyan { background: #e9f8fb; }
.pinned-copy { flex: 1; min-width: 0; }
.pinned-title-line { display: flex; align-items: center; gap: 10rpx; }
.pin-label {
  flex: 0 0 auto;
  padding: 4rpx 9rpx;
  color: #ca8124;
  font-size: 18rpx;
  font-weight: 800;
  background: #fff1dc;
  border-radius: 6rpx;
}
.pinned-title {
  overflow: hidden;
  color: #121820;
  font-size: 27rpx;
  font-weight: 900;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pinned-subtitle {
  display: block;
  margin-top: 7rpx;
  overflow: hidden;
  color: #7e858e;
  font-size: 21rpx;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.category-scroll { width: 100%; margin-top: 36rpx; white-space: nowrap; }
.category-list { display: inline-flex; gap: 14rpx; min-width: 100%; padding: 0 28rpx 8rpx; box-sizing: border-box; }
.category-chip {
  flex: 0 0 auto;
  min-width: 134rpx;
  margin: 0;
  padding: 18rpx 24rpx;
  color: #17212b;
  font-size: 25rpx;
  font-weight: 700;
  line-height: 1;
  background: #ffffff;
  border: 1rpx solid #e4e7eb;
  border-radius: 13rpx;
}
.category-chip::after { border: 0; }
.category-chip--active { color: #ffffff; background: #062a4d; border-color: #062a4d; }
.category-chip--menu { min-width: 70rpx; padding-right: 16rpx; padding-left: 16rpx; }
.feed-list { padding: 16rpx 28rpx 20rpx; }
.feed-card {
  position: relative;
  margin-bottom: 26rpx;
  padding: 28rpx 26rpx 26rpx 30rpx;
  overflow: hidden;
  background: #ffffff;
  border: 1rpx solid #e6e9ed;
  border-radius: 26rpx;
  box-shadow: 0 12rpx 32rpx rgba(9, 36, 64, 0.055);
}
.feed-accent { position: absolute; top: 0; bottom: 0; left: 0; width: 6rpx; background: #0a4c80; }
.feed-head { justify-content: space-between; gap: 16rpx; }
.feed-meta { gap: 15rpx; }
.feed-category { color: #f19127; font-size: 24rpx; font-weight: 900; }
.feed-time { color: #8c929a; font-size: 22rpx; }
.access-badge,
.author-badge {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  padding: 7rpx 12rpx;
  color: #26715f;
  font-size: 19rpx;
  font-weight: 700;
  background: #e8f8f3;
  border-radius: 9rpx;
}
.feed-title { display: block; margin-top: 22rpx; color: #121820; font-size: 33rpx; font-weight: 900; line-height: 1.48; }
.feed-summary {
  display: -webkit-box;
  margin-top: 13rpx;
  overflow: hidden;
  color: #848b94;
  font-size: 25rpx;
  line-height: 1.75;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.engagement-row { gap: 22rpx; margin-top: 24rpx; }
.engagement-item { display: flex; align-items: center; gap: 8rpx; color: #77818b; font-size: 23rpx; }
.author-badge { margin-left: auto; color: #315575; background: #f0f5f9; }
.discussion-box { margin-top: 19rpx; padding: 18rpx 20rpx; background: #f6f7f9; border: 1rpx solid #eceef1; border-radius: 16rpx; }
.liked-line { gap: 8rpx; padding-bottom: 14rpx; color: #315575; font-size: 21rpx; font-weight: 700; border-bottom: 1rpx solid #e0e4e8; }
.comment-line { display: flex; align-items: flex-start; gap: 11rpx; margin-top: 13rpx; color: #3e4853; font-size: 21rpx; line-height: 1.58; }
.comment-avatar { display: flex; flex: 0 0 auto; align-items: center; justify-content: center; width: 31rpx; height: 31rpx; color: #ffffff; font-size: 17rpx; font-weight: 800; background: #39a7c9; border-radius: 50%; }
.comment-author { color: #1a3e60; font-weight: 900; }
.discussion-more { display: block; margin-top: 15rpx; color: #154a75; font-size: 21rpx; font-weight: 800; }
.empty-card { margin: 20rpx 0; padding: 80rpx 30rpx; color: #89929b; text-align: center; background: #ffffff; border-radius: 24rpx; }
</style>
