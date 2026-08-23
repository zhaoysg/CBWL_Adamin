<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { ApiError } from "@/api/http";
import { portalApi } from "@/api/portal";
import type { ContentDetailResponse } from "@/types/portal";
import { formatShortDate } from "@/utils/format";
import { loginUrl } from "@/utils/auth";

const data = ref<ContentDetailResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");
const contentId = ref(0);

async function loadData() {
  if (contentId.value <= 0) {
    errorMessage.value = "内容地址无效";
    loading.value = false;
    return;
  }

  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.content(contentId.value);
  } catch (error) {
    if (error instanceof ApiError && error.statusCode === 401) {
      uni.navigateTo({ url: loginUrl(`/pages/content/detail?id=${contentId.value}`) });
      errorMessage.value = "请登录后继续阅读";
    } else if (error instanceof ApiError && error.statusCode === 403) {
      uni.navigateTo({ url: "/pages/member/index" });
      errorMessage.value = error.message || "当前会员权益不包含该内容";
    } else {
      errorMessage.value = error instanceof Error ? error.message : "内容加载失败";
    }
  } finally {
    loading.value = false;
  }
}

function goBack() {
  uni.navigateBack({
    fail: () => uni.reLaunch({ url: "/pages/home/index" }),
  });
}

function showAction(label: string) {
  uni.showToast({ title: `${label}功能正在接入`, icon: "none" });
}

onLoad((options) => {
  contentId.value = Number(options?.id || 0);
  void loadData();
});
</script>

<template>
  <view class="detail-page">
    <view class="navy-hero article-hero">
      <view class="safe-top" />
      <view class="detail-nav-row">
        <view class="detail-nav-button" @tap="goBack"><AppIcon name="arrow" :size="46" /></view>
        <text class="detail-nav-title">深度内容</text>
        <view class="detail-nav-button" @tap="showAction('更多')">•••</view>
      </view>

      <view v-if="data" class="article-hero-copy">
        <view class="article-meta-row">
          <text class="article-category">#{{ data.category }}</text>
          <view v-if="data.access_level !== 'public'" class="pill member">
            <AppIcon name="lock" :size="20" />
            会员内容
          </view>
          <view v-else class="pill">公开内容</view>
        </view>
        <text class="article-title">{{ data.title }}</text>
        <text class="article-summary">{{ data.summary }}</text>
        <view class="author-row">
          <view class="author-avatar">{{ data.author.avatar_text }}</view>
          <view class="author-copy">
            <text class="author-name">{{ data.author.name }} · {{ data.author.title }}</text>
            <text class="author-meta">{{ formatShortDate(data.published_at) }} · 阅读约 {{ data.reading_minutes }} 分钟</text>
          </view>
        </view>
      </view>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />

    <view v-else-if="data" class="article-body">
      <rich-text v-if="data.body_html" class="article-rich-text" :nodes="data.body_html" />
      <template v-else>
        <view
          v-for="(section, index) in data.sections"
          :key="`${section.heading}-${index}`"
          class="article-section"
        >
          <text v-if="section.heading" class="article-heading">{{ section.heading }}</text>
          <text v-for="paragraph in section.paragraphs" :key="paragraph" class="article-paragraph">
            {{ paragraph }}
          </text>
        </view>
      </template>

      <view class="risk-note">
        本文仅用于会员投研交流与教育，不构成任何投资建议。市场有风险，决策需独立判断。
      </view>

      <view class="article-actions surface-card">
        <view class="article-action" @tap="showAction('点赞')">
          <AppIcon name="like" :size="38" />
          <text>{{ data.like_count }}</text>
        </view>
        <view class="article-action" @tap="showAction('评论')">
          <AppIcon name="comment" :size="34" />
          <text>{{ data.comment_count }}</text>
        </view>
        <view class="article-action" @tap="showAction('收藏')">
          <AppIcon name="star" :size="32" />
          <text>收藏</text>
        </view>
        <view class="article-action" @tap="showAction('分享')">
          <AppIcon name="share" :size="32" />
          <text>分享</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped lang="scss">
.detail-page {
  min-height: 100vh;
  padding-bottom: calc(42rpx + env(safe-area-inset-bottom));
  background: #fff;
}

.article-hero {
  padding-bottom: 44rpx;
}

.detail-nav-row,
.article-meta-row,
.author-row,
.article-actions,
.article-action {
  display: flex;
  align-items: center;
}

.detail-nav-row,
.article-meta-row {
  justify-content: space-between;
}

.detail-nav-row {
  position: relative;
  z-index: 2;
  padding: 24rpx 30rpx 0;
}

.detail-nav-button {
  display: flex;
  width: 68rpx;
  height: 68rpx;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
  font-size: 26rpx;
  font-weight: 800;
}

.detail-nav-button:first-child {
  transform: rotate(180deg);
}

.detail-nav-title {
  color: rgba(255, 255, 255, 0.82);
  font-size: 25rpx;
  font-weight: 800;
}

.article-hero-copy {
  position: relative;
  z-index: 2;
  padding: 38rpx 32rpx 0;
}

.article-meta-row {
  gap: 18rpx;
}

.article-category {
  color: #ffb12d;
  font-size: 23rpx;
  font-weight: 900;
}

.article-title,
.article-summary,
.author-name,
.author-meta,
.article-heading,
.article-paragraph {
  display: block;
}

.article-title {
  margin-top: 20rpx;
  font-size: 42rpx;
  font-weight: 900;
  line-height: 1.42;
}

.article-summary {
  margin-top: 16rpx;
  color: rgba(255, 255, 255, 0.72);
  font-size: 24rpx;
  line-height: 1.72;
}

.author-row {
  margin-top: 30rpx;
  gap: 14rpx;
}

.author-avatar {
  display: flex;
  width: 62rpx;
  height: 62rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2rpx solid rgba(255, 255, 255, 0.22);
  border-radius: 50%;
  color: #fff;
  background: rgba(255, 255, 255, 0.13);
  font-size: 24rpx;
  font-weight: 900;
}

.author-copy {
  min-width: 0;
}

.author-name {
  font-size: 23rpx;
  font-weight: 800;
}

.author-meta {
  margin-top: 5rpx;
  color: rgba(255, 255, 255, 0.52);
  font-size: 19rpx;
}

.article-body {
  padding: 10rpx 32rpx 40rpx;
  color: #293540;
}

.article-rich-text {
  display: block;
  padding-top: 30rpx;
  color: #293540;
  font-size: 26rpx;
  line-height: 1.9;
  word-break: break-word;
}

.article-section {
  padding-top: 30rpx;
}

.article-heading {
  position: relative;
  padding-left: 20rpx;
  color: #151a22;
  font-size: 31rpx;
  font-weight: 900;

  &::before {
    position: absolute;
    top: 4rpx;
    bottom: 4rpx;
    left: 0;
    width: 7rpx;
    border-radius: 8rpx;
    background: #ff9a22;
    content: "";
  }
}

.article-paragraph {
  margin-top: 20rpx;
  font-size: 26rpx;
  line-height: 1.9;
  text-align: justify;
}

.risk-note {
  margin-top: 42rpx;
  padding: 22rpx;
  border: 1rpx solid #f4dfb8;
  border-radius: 18rpx;
  color: #8a6739;
  background: #fff8e9;
  font-size: 21rpx;
  line-height: 1.68;
}

.article-actions {
  margin-top: 28rpx;
  padding: 18rpx 8rpx;
  justify-content: space-around;
}

.article-action {
  min-width: 104rpx;
  flex-direction: column;
  justify-content: center;
  gap: 8rpx;
  color: #65717e;
  font-size: 20rpx;
}
</style>
