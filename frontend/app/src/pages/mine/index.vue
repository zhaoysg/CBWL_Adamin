<script setup lang="ts">
import { onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import BottomNav from "@/components/BottomNav.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { portalApi } from "@/api/portal";
import type { ProfileResponse } from "@/types/portal";
import { formatRelativeTime } from "@/utils/format";

const data = ref<ProfileResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");

const achievementGlyphs: Record<string, string> = {
  fire: "♨",
  wave: "∿",
  chip: "▦",
  crown: "♛",
};

const assetIconMap: Record<string, string> = {
  note: "note",
  download: "download",
  star: "star",
};

async function loadData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.profile();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "未知错误";
  } finally {
    loading.value = false;
  }
}

function showComingSoon(label: string) {
  uni.showToast({ title: `${label}功能正在接入`, icon: "none" });
}

onMounted(loadData);
</script>

<template>
  <view class="page-shell mine-page">
    <view v-if="data" class="navy-hero profile-hero">
      <view class="safe-top" />
      <view class="profile-header-row">
        <text class="page-title">个人中心</text>
        <view class="profile-actions">
          <view class="glass-icon-button notification" @tap="showComingSoon('通知')">
            <AppIcon name="bell" :size="24" />
            <view class="notice-dot" />
          </view>
          <view class="glass-icon-button" @tap="showComingSoon('设置')">⚙</view>
        </view>
      </view>

      <view class="profile-user-row" @tap="showComingSoon('个人资料')">
        <view class="profile-avatar">
          <view class="avatar-crown">♛</view>
        </view>
        <view class="profile-user-copy">
          <view class="nickname-line">
            <text class="nickname">{{ data.member.nickname }}</text>
            <view class="verified">✓</view>
          </view>
          <text class="profile-slogan">{{ data.member.slogan }}</text>
          <view class="member-number-line">
            <text class="member-number">{{ data.member.member_no }}</text>
            <text class="joined-days">同行 {{ data.member.joined_days }} 天</text>
          </view>
        </view>
        <AppIcon class="profile-arrow" name="arrow" :size="46" />
      </view>

      <view class="membership-card">
        <view class="membership-top">
          <view class="membership-title"><AppIcon name="crown" :size="38" />{{ data.member.level_name }}</view>
          <button class="privilege-button" @tap="showComingSoon('特权中心')">特权中心 ›</button>
        </view>
        <view class="benefit-line">
          <view class="benefit-list">
            <text v-for="benefit in data.benefits" :key="benefit" class="benefit-item">▤ {{ benefit }}</text>
          </view>
          <text class="expire-date">{{ data.member.expire_date }} 到期</text>
        </view>
      </view>
    </view>

    <view v-if="data" class="profile-body">
      <view class="surface-card stats-card">
        <view class="stat-block">
          <text class="stat-value">{{ data.stats.learning_courses }}<text class="stat-unit">门</text></text>
          <text class="stat-label">在学课程</text>
        </view>
        <view class="stat-divider" />
        <view class="stat-block">
          <text class="stat-value">{{ data.stats.reading_columns }}<text class="stat-unit">个</text></text>
          <text class="stat-label">专栏研读</text>
        </view>
        <view class="stat-divider" />
        <view class="stat-block">
          <text class="stat-value">{{ data.stats.replay_count }}<text class="stat-unit">期</text></text>
          <text class="stat-label">直播回看</text>
        </view>
        <view class="stat-divider" />
        <view class="stat-block">
          <text class="stat-value">{{ data.stats.learning_hours }}<text class="stat-unit">h</text></text>
          <text class="stat-label">研学时长</text>
        </view>
      </view>

      <view class="surface-card recent-card">
        <view class="recent-heading">
          <view class="recent-title"><view class="play-dot">▶</view>最近在学</view>
          <text class="recent-time">{{ formatRelativeTime(data.recent_learning.last_studied_at) }}</text>
        </view>
        <view class="recent-course-line">
          <text class="pill orange">{{ data.recent_learning.category }}</text>
          <text class="recent-course-title">{{ data.recent_learning.title }}</text>
        </view>
        <text class="recent-lesson">{{ data.recent_learning.lesson_title }}</text>
        <view class="progress-action-row">
          <view class="progress-area">
            <view class="progress-track"><view class="progress-value" :style="{ width: `${data.recent_learning.progress}%` }" /></view>
            <view class="progress-meta">
              <text>已学 {{ data.recent_learning.learned_lessons }}/{{ data.recent_learning.total_lessons }} 讲</text>
              <text class="progress-percent">{{ data.recent_learning.progress }}%</text>
            </view>
          </view>
          <button class="continue-button" @tap="showComingSoon('继续学习')">▶ 继续学习</button>
        </view>
      </view>

      <view class="surface-card achievement-card">
        <view class="achievement-heading">
          <view class="achievement-title"><text class="medal-icon">✥</text>投研成就勋章</view>
          <text class="achievement-count">已点亮 3/4 ›</text>
        </view>
        <view class="achievement-list">
          <view v-for="achievement in data.achievements" :key="achievement.code" class="achievement-item" :class="{ locked: !achievement.unlocked }">
            <view class="achievement-icon" :class="`achievement-${achievement.icon}`">
              {{ achievementGlyphs[achievement.icon] || '◆' }}
            </view>
            <text class="achievement-name">{{ achievement.name }}</text>
          </view>
        </view>
      </view>

      <text class="assets-heading">投研资产与记录</text>
      <view class="surface-card assets-card">
        <view
          v-for="(asset, index) in data.assets"
          :key="asset.title"
          class="asset-row"
          :class="{ 'with-divider': index > 0 }"
          @tap="showComingSoon(asset.title)"
        >
          <view class="asset-icon"><AppIcon :name="assetIconMap[asset.icon] || 'note'" :size="34" /></view>
          <text class="asset-title">{{ asset.title }}</text>
          <view class="asset-meta">
            <text>{{ asset.meta }}</text>
            <text v-if="asset.badge" class="asset-badge">{{ asset.badge }}</text>
          </view>
          <AppIcon class="asset-arrow" name="arrow" :size="38" />
        </view>
      </view>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />
    <BottomNav active="mine" />
  </view>
</template>

<style scoped lang="scss">
.profile-hero {
  min-height: 570rpx;
  padding-bottom: 34rpx;
}

.profile-header-row,
.profile-actions,
.profile-user-row,
.nickname-line,
.member-number-line,
.membership-top,
.membership-title,
.benefit-line,
.stats-card,
.recent-heading,
.recent-title,
.recent-course-line,
.progress-action-row,
.progress-meta,
.achievement-heading,
.achievement-title,
.achievement-list,
.asset-row,
.asset-meta {
  display: flex;
  align-items: center;
}

.profile-header-row,
.membership-top,
.benefit-line,
.recent-heading,
.progress-meta,
.achievement-heading {
  justify-content: space-between;
}

.profile-header-row {
  position: relative;
  z-index: 2;
  padding: 30rpx 30rpx 0;
}

.page-title {
  font-size: 36rpx;
  font-weight: 900;
}

.profile-actions {
  gap: 12rpx;
}

.notification {
  position: relative;
}

.notice-dot {
  position: absolute;
  top: 7rpx;
  right: 8rpx;
  width: 14rpx;
  height: 14rpx;
  border: 3rpx solid #0a3158;
  border-radius: 50%;
  background: #ff4755;
}

.profile-user-row {
  position: relative;
  z-index: 2;
  padding: 44rpx 30rpx 28rpx;
  gap: 22rpx;
}

.profile-avatar {
  position: relative;
  width: 112rpx;
  height: 112rpx;
  flex: 0 0 auto;
  border: 4rpx solid #ffbf2b;
  border-radius: 50%;
  background: linear-gradient(145deg, #ff9d15, #ff7d1d);
  box-shadow: 0 12rpx 30rpx rgba(255, 135, 18, 0.24);
}

.avatar-crown {
  position: absolute;
  right: -5rpx;
  bottom: -5rpx;
  display: flex;
  width: 38rpx;
  height: 38rpx;
  align-items: center;
  justify-content: center;
  border: 4rpx solid #062645;
  border-radius: 50%;
  color: #ffc62e;
  background: #0a2f54;
  font-size: 21rpx;
}

.profile-user-copy {
  min-width: 0;
  flex: 1;
}

.nickname-line {
  gap: 10rpx;
}

.nickname {
  max-width: 440rpx;
  overflow: hidden;
  font-size: 32rpx;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.verified {
  display: flex;
  width: 28rpx;
  height: 28rpx;
  align-items: center;
  justify-content: center;
  border-radius: 8rpx;
  color: #432900;
  background: #ff9225;
  font-size: 18rpx;
  font-weight: 900;
}

.profile-slogan {
  display: block;
  margin-top: 8rpx;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.72);
  font-size: 22rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-number-line {
  margin-top: 10rpx;
  gap: 14rpx;
}

.member-number {
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  color: #ffe25c;
  background: rgba(255, 218, 54, 0.1);
  font-family: monospace;
  font-size: 20rpx;
  font-weight: 800;
}

.joined-days {
  color: rgba(255, 255, 255, 0.65);
  font-size: 20rpx;
}

.profile-arrow {
  color: rgba(255, 255, 255, 0.6);
}

.membership-card {
  position: relative;
  z-index: 2;
  margin: 0 30rpx;
  padding: 30rpx 28rpx 24rpx;
  overflow: hidden;
  border: 1rpx solid rgba(255, 198, 54, 0.52);
  border-radius: 28rpx;
  color: #ffe27a;
  background:
    radial-gradient(circle at 94% 0%, rgba(255, 186, 48, 0.15), transparent 28%),
    linear-gradient(135deg, #1b1811, #2f2516);
  box-shadow: 0 18rpx 44rpx rgba(0, 0, 0, 0.24);
}

.membership-title {
  gap: 12rpx;
  font-size: 31rpx;
  font-weight: 900;
}

.privilege-button {
  height: 56rpx;
  padding: 0 18rpx;
  border: none;
  border-radius: 30rpx;
  color: #4b3000;
  background: linear-gradient(90deg, #ffe04a, #ff9e18);
  font-size: 21rpx;
  font-weight: 900;
}

.benefit-line {
  margin-top: 26rpx;
  padding-top: 18rpx;
  gap: 18rpx;
  border-top: 1rpx solid rgba(255, 225, 117, 0.16);
}

.benefit-list {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
  gap: 10rpx 18rpx;
}

.benefit-item {
  color: rgba(255, 239, 189, 0.78);
  font-size: 19rpx;
}

.expire-date {
  flex: 0 0 auto;
  color: #d9c75f;
  font-size: 20rpx;
}

.profile-body {
  padding: 22rpx 30rpx 42rpx;
}

.stats-card {
  min-height: 126rpx;
  padding: 22rpx 10rpx;
}

.stat-block {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.stat-value,
.stat-label {
  display: block;
}

.stat-value {
  color: #12161d;
  font-size: 38rpx;
  font-weight: 900;
}

.stat-unit {
  margin-left: 4rpx;
  color: #727b86;
  font-size: 18rpx;
  font-weight: 600;
}

.stat-label {
  margin-top: 4rpx;
  color: #6f7884;
  font-size: 20rpx;
}

.stat-divider {
  width: 1rpx;
  height: 64rpx;
  background: #dfe4e9;
}

.recent-card,
.achievement-card {
  margin-top: 22rpx;
  padding: 28rpx;
}

.recent-title,
.achievement-title {
  gap: 12rpx;
  color: #171b22;
  font-size: 28rpx;
  font-weight: 900;
}

.play-dot {
  display: flex;
  width: 34rpx;
  height: 34rpx;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #ff9a2b;
  font-size: 15rpx;
}

.recent-time {
  color: #89919b;
  font-size: 21rpx;
}

.recent-course-line {
  margin-top: 18rpx;
  gap: 12rpx;
}

.recent-course-title {
  min-width: 0;
  overflow: hidden;
  font-size: 29rpx;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-lesson {
  display: block;
  margin-top: 8rpx;
  color: #747d88;
  font-size: 22rpx;
  line-height: 1.55;
}

.progress-action-row {
  margin-top: 22rpx;
  gap: 22rpx;
}

.progress-area {
  min-width: 0;
  flex: 1;
}

.progress-track {
  height: 12rpx;
  overflow: hidden;
  border-radius: 8rpx;
  background: #e9edf1;
}

.progress-value {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffad2e, #ff761c);
}

.progress-meta {
  margin-top: 8rpx;
  color: #7a828d;
  font-size: 20rpx;
}

.progress-percent {
  color: #f28a1d;
  font-weight: 900;
}

.continue-button {
  flex: 0 0 auto;
  height: 62rpx;
  padding: 0 22rpx;
  border: none;
  border-radius: 34rpx;
  color: #fff;
  background: #052f58;
  font-size: 21rpx;
  font-weight: 900;
}

.achievement-heading {
  gap: 16rpx;
}

.medal-icon {
  color: #f5a121;
}

.achievement-count {
  color: #173f61;
  font-size: 21rpx;
  font-weight: 700;
}

.achievement-list {
  margin-top: 28rpx;
  justify-content: space-between;
  gap: 12rpx;
}

.achievement-item {
  display: flex;
  width: 25%;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
}

.achievement-icon {
  display: flex;
  width: 76rpx;
  height: 76rpx;
  align-items: center;
  justify-content: center;
  border: 2rpx solid currentColor;
  border-radius: 50%;
  font-size: 34rpx;
  box-shadow: inset 0 0 0 10rpx rgba(255, 255, 255, 0.6);
}

.achievement-fire { color: #f1a026; background: #fff3e3; }
.achievement-wave { color: #2f98c4; background: #e9f6fb; }
.achievement-chip { color: #33b997; background: #e7f8f3; }
.achievement-crown { color: #8d96a3; background: #eef0f2; }

.achievement-item.locked {
  opacity: 0.48;
}

.achievement-name {
  color: #20262e;
  font-size: 19rpx;
  font-weight: 700;
  text-align: center;
}

.assets-heading {
  display: block;
  margin: 34rpx 8rpx 14rpx;
  color: #747d87;
  font-size: 24rpx;
  font-weight: 800;
}

.assets-card {
  padding: 0 26rpx;
}

.asset-row {
  min-height: 98rpx;
  gap: 16rpx;
}

.asset-row.with-divider {
  border-top: 1rpx solid #e4e8ec;
}

.asset-icon {
  display: flex;
  width: 50rpx;
  height: 50rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 14rpx;
  color: #1c567c;
  background: #edf4f8;
}

.asset-title {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-size: 24rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-meta {
  flex: 0 0 auto;
  gap: 8rpx;
  color: #7b8490;
  font-size: 20rpx;
}

.asset-badge {
  padding: 3rpx 8rpx;
  border-radius: 7rpx;
  color: #e18a29;
  background: #fff1e2;
  font-weight: 800;
}

.asset-arrow {
  flex: 0 0 auto;
  color: #969da6;
}
</style>
