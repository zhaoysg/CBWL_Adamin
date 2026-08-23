<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ApiError } from "../../api/http";
import { authApi } from "../../api/auth";
import { portalApi } from "../../api/portal";
import type { ProfileResponse } from "../../types/portal";
import CwBottomNav from "../../components/portal/CwBottomNav.vue";
import CwIcon from "../../components/portal/CwIcon.vue";
import CwPageState from "../../components/portal/CwPageState.vue";
import { formatHours } from "../../utils/portal-format";
import { loginUrl } from "../../utils/auth";

const data = ref<ProfileResponse>();
const loading = ref(true);
const error = ref("");
const requiresLogin = ref(false);

async function load() {
  loading.value = true;
  error.value = "";
  requiresLogin.value = false;
  try {
    data.value = await portalApi.profile();
  } catch (reason) {
    data.value = undefined;
    if (reason instanceof ApiError && reason.statusCode === 401) {
      requiresLogin.value = true;
    } else {
      error.value = reason instanceof Error ? reason.message : "网络连接失败";
    }
  } finally {
    loading.value = false;
  }
}

function openLogin() {
  uni.navigateTo({ url: loginUrl("/pages/mine/index") });
}

function openMemberCenter() {
  uni.navigateTo({ url: "/pages/member/index" });
}

function continueLearning() {
  const recent = data.value?.recent_learning;
  if (!recent) return;
  uni.navigateTo({ url: `/pages/course/detail?id=${recent.course_id}` });
}

function openAsset(title: string) {
  uni.showToast({ title: `${title}功能正在接入`, icon: "none" });
}

async function logout() {
  const confirmed = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: "退出登录",
      content: "退出后需要重新登录才能查看会员内容，确定继续吗？",
      success: (result) => resolve(Boolean(result.confirm)),
      fail: () => resolve(false),
    });
  });
  if (!confirmed) return;
  try {
    await authApi.logout();
  } finally {
    data.value = undefined;
    requiresLogin.value = true;
    uni.showToast({ title: "已退出登录", icon: "none" });
  }
}

onShow(() => {
  uni.hideTabBar({ animation: false, fail: () => undefined });
  void load();
});
</script>

<template>
  <view class="mine-page">
    <view class="profile-hero">
      <view class="profile-header">
        <text class="profile-page-title">个人中心</text>
        <view class="profile-actions">
          <button class="round-action round-action--dot"><CwIcon name="bell" :size="29" tone="white" /></button>
          <button class="round-action"><CwIcon name="settings" :size="32" tone="white" /></button>
        </view>
      </view>

      <CwPageState v-if="loading || error" :loading="loading" :error="error" dark @retry="load" />
      <view v-else-if="requiresLogin" class="login-panel">
        <text class="login-panel__title">登录后查看个人中心</text>
        <text class="login-panel__copy">会员权益、内容访问和订阅有效期均以登录账号为准。</text>
        <button class="login-panel__button" @tap="openLogin">立即登录</button>
      </view>
      <template v-else-if="data">
        <view class="member-profile">
          <view class="profile-avatar">
            <view class="avatar-crown"><CwIcon name="crown" :size="25" tone="gold" /></view>
          </view>
          <view class="profile-copy">
            <view class="nickname-row"><text class="nickname">{{ data.member.nickname }}</text><text class="verified">✓</text></view>
            <text class="member-slogan">{{ data.member.slogan }}</text>
            <view class="member-meta"><text class="member-number">{{ data.member.member_no }}</text><text>同行 {{ data.member.joined_days }} 天</text></view>
          </view>
          <CwIcon name="arrow" :size="50" tone="white" />
        </view>

        <view class="membership-card" @tap="openMemberCenter">
          <view class="membership-top">
            <view class="membership-name"><CwIcon name="crown" :size="38" tone="gold" /><text>{{ data.member.level_name }}</text></view>
            <button class="privilege-button">特权中心 ›</button>
          </view>
          <view class="membership-benefits">
            <text v-for="benefit in data.benefits" :key="benefit">{{ benefit }}</text>
            <text v-if="!data.benefits.length" class="benefit-empty">当前账号暂无会员权益</text>
            <text class="expire-date">{{ data.member.expire_date ? `${data.member.expire_date} 到期` : "尚未开通会员" }}</text>
          </view>
        </view>
      </template>
    </view>

    <view v-if="data" class="profile-content">
      <view class="stats-card">
        <view class="stat"><text class="stat-value">{{ data.stats.learning_courses }}<small>门</small></text><text class="stat-label">在学课程</text></view>
        <view class="stat"><text class="stat-value">{{ data.stats.reading_columns }}<small>个</small></text><text class="stat-label">专栏研读</text></view>
        <view class="stat"><text class="stat-value">{{ data.stats.replay_count }}<small>期</small></text><text class="stat-label">直播回看</text></view>
        <view class="stat"><text class="stat-value">{{ formatHours(data.stats.learning_hours) }}<small>h</small></text><text class="stat-label">研学时长</text></view>
      </view>

      <section v-if="data.recent_learning" class="panel recent-panel">
        <view class="panel-heading">
          <view class="panel-title"><view class="orange-play"><CwIcon name="play" :size="20" tone="white" /></view><text>最近在学</text></view>
          <text class="panel-time">昨天 21:30</text>
        </view>
        <view class="recent-course-row">
          <text class="recent-category">{{ data.recent_learning.category }}</text>
          <text class="recent-course">{{ data.recent_learning.title }}</text>
        </view>
        <text class="lesson-name">{{ data.recent_learning.lesson_title }}</text>
        <view class="progress-row">
          <view class="progress-track"><view class="progress-value" :style="{ width: `${data.recent_learning.progress}%` }" /></view>
          <text class="lesson-count">已学 {{ data.recent_learning.learned_lessons }}/{{ data.recent_learning.total_lessons }} 讲</text>
          <text class="progress-percent">{{ data.recent_learning.progress }}%</text>
          <button class="continue-button" @tap="continueLearning"><CwIcon name="play" :size="20" tone="white" /><text>继续学习</text></button>
        </view>
      </section>

      <section class="panel achievements-panel">
        <view class="panel-heading">
          <view class="panel-title"><text class="medal">◉</text><text>投研成就勋章</text></view>
          <text class="panel-link">已点亮 {{ data.achievements.filter((item) => item.unlocked).length }}/{{ data.achievements.length }} ›</text>
        </view>
        <view class="achievement-grid">
          <view v-for="item in data.achievements" :key="item.code" class="achievement" :class="{ 'achievement--locked': !item.unlocked }">
            <view class="achievement-icon" :class="`achievement-icon--${item.icon}`"><CwIcon :name="item.icon" :size="43" :tone="item.unlocked ? (item.icon === 'chip' ? 'green' : item.icon === 'wave' ? 'cyan' : 'orange') : 'muted'" /></view>
            <text>{{ item.name }}</text>
          </view>
        <view v-if="!data.achievements.length" class="empty-panel">成就体系将在学习模块上线后开放</view>
        </view>
      </section>

      <text class="group-title">投研资产与记录</text>
      <section class="panel asset-panel">
        <view v-if="!data.assets.length" class="empty-panel">暂无投研资产记录</view>
        <button v-for="asset in data.assets" :key="asset.title" class="asset-row" hover-class="asset-row--hover" @tap="openAsset(asset.title)">
          <view class="asset-icon" :class="`asset-icon--${asset.icon}`"><CwIcon :name="asset.icon" :size="33" :tone="asset.icon === 'star' ? 'gold' : asset.icon === 'download' ? 'cyan' : 'navy'" /></view>
          <text class="asset-title">{{ asset.title }}</text>
          <text class="asset-meta">{{ asset.meta }}</text>
          <text v-if="asset.badge" class="asset-badge">{{ asset.badge }}</text>
          <CwIcon name="arrow" :size="42" tone="muted" />
        </button>
      </section>

      <text class="group-title group-title--light">社区互动与交流</text>
      <button class="logout-button" @tap="logout">退出登录</button>
    </view>

    <CwBottomNav active="mine" />
  </view>
</template>

<style scoped lang="scss">
.mine-page { min-height: 100vh; padding-bottom: 170rpx; background: #f5f7fa; }
.profile-hero {
  padding: calc(var(--status-bar-height) + 38rpx) 30rpx 58rpx;
  color: #ffffff;
  background:
    radial-gradient(circle at 88% 15%, rgba(36, 91, 139, 0.34), transparent 38%),
    linear-gradient(145deg, #031a34, #062a4d 63%, #0b3b65);
}
.profile-header, .profile-actions, .member-profile, .nickname-row, .member-meta, .membership-top, .membership-name, .membership-benefits, .panel-heading, .panel-title, .recent-course-row, .progress-row, .asset-row { display: flex; align-items: center; }
.profile-header { justify-content: space-between; }
.profile-page-title { font-size: 38rpx; font-weight: 900; }
.profile-actions { gap: 13rpx; }
.round-action { position: relative; display: flex; align-items: center; justify-content: center; width: 72rpx; height: 72rpx; margin: 0; padding: 0; background: rgba(255,255,255,.08); border: 1rpx solid rgba(255,255,255,.14); border-radius: 50%; }
.round-action::after, .privilege-button::after, .continue-button::after, .asset-row::after { border: 0; }
.round-action--dot::before { position: absolute; top: 6rpx; right: 7rpx; width: 12rpx; height: 12rpx; content: ""; background: #ff4256; border: 3rpx solid #0a3157; border-radius: 50%; }
.member-profile { gap: 22rpx; margin-top: 36rpx; }
.profile-avatar { position: relative; flex: 0 0 auto; width: 112rpx; height: 112rpx; background: linear-gradient(145deg,#ffba23,#ff7d16); border: 4rpx solid #ffce3a; border-radius: 50%; box-shadow: 0 10rpx 24rpx rgba(255,142,21,.25); }
.avatar-crown { position: absolute; right: -5rpx; bottom: -3rpx; display: flex; align-items: center; justify-content: center; width: 41rpx; height: 41rpx; background: #082c51; border: 3rpx solid #092746; border-radius: 50%; }
.profile-copy { flex: 1; min-width: 0; }
.nickname-row { gap: 10rpx; }
.nickname { overflow: hidden; font-size: 35rpx; font-weight: 900; white-space: nowrap; text-overflow: ellipsis; }
.verified { display: inline-flex; align-items: center; justify-content: center; width: 27rpx; height: 27rpx; color: #ffffff; font-size: 17rpx; font-weight: 900; background: #ff8a22; border-radius: 50%; }
.member-slogan { display: block; margin-top: 7rpx; overflow: hidden; color: rgba(255,255,255,.66); font-size: 21rpx; white-space: nowrap; text-overflow: ellipsis; }
.member-meta { gap: 18rpx; margin-top: 10rpx; color: rgba(255,255,255,.62); font-size: 20rpx; }
.member-number { padding: 4rpx 8rpx; color: #ffe36b; font-family: monospace; background: rgba(255,211,45,.1); border-radius: 5rpx; }
.membership-card { margin-top: 31rpx; padding: 30rpx 27rpx 26rpx; overflow: hidden; background: linear-gradient(105deg,#171711,#2f2417 55%,#1b1c18); border: 1rpx solid rgba(235,185,43,.5); border-radius: 26rpx; box-shadow: 0 15rpx 35rpx rgba(0,0,0,.22); }
.membership-top { justify-content: space-between; gap: 15rpx; }
.membership-name { gap: 12rpx; color: #ffe67c; font-size: 31rpx; font-weight: 900; }
.privilege-button { margin: 0; padding: 12rpx 18rpx; color: #3b2a04; font-size: 20rpx; font-weight: 900; line-height: 1; background: linear-gradient(105deg,#ffe54b,#ff9b1d); border: 0; border-radius: 28rpx; }
.membership-benefits { flex-wrap: wrap; gap: 17rpx; margin-top: 27rpx; padding-top: 21rpx; color: rgba(255,255,255,.73); font-size: 19rpx; border-top: 1rpx solid rgba(255,255,255,.1); }
.expire-date { margin-left: auto; color: #d1b94d; }
.profile-content { padding: 0 30rpx 30rpx; }
.stats-card { display: grid; grid-template-columns: repeat(4,1fr); margin-top: 26rpx; padding: 27rpx 8rpx; background: #ffffff; border: 1rpx solid #e7eaee; border-radius: 25rpx; box-shadow: 0 10rpx 26rpx rgba(8,39,70,.055); }
.stat { position: relative; display: flex; flex-direction: column; align-items: center; gap: 7rpx; }
.stat + .stat::before { position: absolute; top: 5rpx; bottom: 5rpx; left: 0; width: 1rpx; content: ""; background: #e1e4e8; }
.stat-value { color: #111820; font-size: 39rpx; font-weight: 900; line-height: 1; }
.stat-value small { margin-left: 2rpx; color: #777f88; font-size: 18rpx; font-weight: 500; }
.stat-label { color: #6f7882; font-size: 20rpx; }
.panel { margin-top: 25rpx; padding: 27rpx; background: #ffffff; border: 1rpx solid #e6e9ed; border-radius: 24rpx; box-shadow: 0 10rpx 25rpx rgba(8,39,70,.05); }
.panel-heading { justify-content: space-between; gap: 14rpx; }
.panel-title { gap: 10rpx; color: #151c23; font-size: 29rpx; font-weight: 900; }
.panel-time, .panel-link { color: #818a94; font-size: 20rpx; }
.panel-link { color: #174a76; font-weight: 700; }
.orange-play { display: flex; align-items: center; justify-content: center; width: 32rpx; height: 32rpx; background: #ff941f; border-radius: 50%; }
.recent-course-row { gap: 12rpx; margin-top: 21rpx; }
.recent-category { padding: 5rpx 9rpx; color: #ee8b22; font-size: 19rpx; background: #fff4e6; border-radius: 5rpx; }
.recent-course { color: #141b22; font-size: 29rpx; font-weight: 900; }
.lesson-name { display: block; margin-top: 9rpx; color: #747d87; font-size: 22rpx; line-height: 1.55; }
.progress-row { flex-wrap: wrap; gap: 11rpx; margin-top: 20rpx; }
.progress-track { flex: 1 1 260rpx; height: 10rpx; overflow: hidden; background: #edf0f2; border-radius: 10rpx; }
.progress-value { height: 100%; background: linear-gradient(90deg,#ffad24,#ff6f14); border-radius: inherit; }
.lesson-count { color: #7b848e; font-size: 19rpx; }
.progress-percent { color: #f28d23; font-size: 22rpx; font-weight: 900; }
.continue-button { display: flex; align-items: center; gap: 7rpx; margin: 0 0 0 auto; padding: 13rpx 19rpx; color: #ffffff; font-size: 20rpx; font-weight: 800; line-height: 1; background: #082f57; border: 0; border-radius: 27rpx; }
.medal { color: #f5a623; font-size: 31rpx; }
.achievement-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12rpx; margin-top: 26rpx; }
.achievement { display: flex; flex-direction: column; align-items: center; gap: 10rpx; color: #1d252d; font-size: 19rpx; font-weight: 700; text-align: center; }
.achievement--locked { color: #9fa5ac; }
.achievement-icon { display: flex; align-items: center; justify-content: center; width: 76rpx; height: 76rpx; background: #fff5e8; border: 2rpx solid #f6d5ad; border-radius: 50%; }
.achievement-icon--wave { background: #eaf8fc; border-color: #b8e2ec; }
.achievement-icon--chip { background: #eaf9f4; border-color: #b9e7d8; }
.achievement--locked .achievement-icon { background: #f1f2f3; border-color: #e2e4e6; }
.group-title { display: block; margin: 33rpx 7rpx 14rpx; color: #6f7882; font-size: 23rpx; font-weight: 700; }
.group-title--light { color: #9aa1a9; }
.asset-panel { margin-top: 0; padding: 0 25rpx; overflow: hidden; }
.asset-row { width: 100%; min-height: 100rpx; margin: 0; padding: 19rpx 0; text-align: left; background: transparent; border: 0; border-radius: 0; }
.asset-row + .asset-row { border-top: 1rpx solid #e5e8eb; }
.asset-row--hover { background: #f8fafb; }
.asset-icon { display: flex; align-items: center; justify-content: center; width: 54rpx; height: 54rpx; margin-right: 16rpx; background: #edf4fa; border-radius: 13rpx; }
.asset-icon--download { background: #e8f8fb; }
.asset-icon--star { background: #fff8e5; }
.asset-title { flex: 1; min-width: 0; color: #1a222a; font-size: 24rpx; font-weight: 800; }
.asset-meta { margin-left: 10rpx; color: #858d96; font-size: 20rpx; }
.asset-badge { margin-left: 10rpx; padding: 5rpx 9rpx; color: #e88b2d; font-size: 17rpx; background: #fff3e5; border-radius: 5rpx; }
.login-panel { margin-top: 34rpx; padding: 30rpx; text-align: center; background: rgba(255,255,255,.09); border: 1rpx solid rgba(255,255,255,.16); border-radius: 24rpx; }
.login-panel__title, .login-panel__copy { display: block; }
.login-panel__title { font-size: 30rpx; font-weight: 900; }
.login-panel__copy { margin-top: 10rpx; color: rgba(255,255,255,.68); font-size: 21rpx; line-height: 1.6; }
.login-panel__button { width: 220rpx; margin: 24rpx auto 0; color: #082f57; font-size: 22rpx; font-weight: 900; background: linear-gradient(105deg,#ffe54b,#ff9b1d); border: 0; border-radius: 32rpx; }
.login-panel__button::after, .logout-button::after { border: 0; }
.benefit-empty { color: rgba(255,255,255,.58); }
.empty-panel { width: 100%; padding: 30rpx 10rpx; color: #8a939d; font-size: 21rpx; text-align: center; }
.logout-button { margin: 30rpx 0 0; color: #b34a4a; font-size: 22rpx; font-weight: 800; background: #fff; border: 1rpx solid #efd5d5; border-radius: 20rpx; }
</style>
