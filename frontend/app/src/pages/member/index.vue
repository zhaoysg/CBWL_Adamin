<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { portalApi } from "@/api/portal";
import type { MemberCenterResponse } from "@/types/portal";

const data = ref<MemberCenterResponse | null>(null);
const loading = ref(true);
const errorMessage = ref("");
const selectedPlanCode = ref("year");

const selectedPlan = computed(() =>
  data.value?.plans.find((plan) => plan.code === selectedPlanCode.value),
);

async function loadData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    data.value = await portalApi.memberCenter();
    const recommended = data.value.plans.find((plan) => plan.recommended);
    selectedPlanCode.value = recommended?.code || data.value.plans[0]?.code || "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "会员中心加载失败";
  } finally {
    loading.value = false;
  }
}

function goBack() {
  uni.navigateBack({
    fail: () => uni.reLaunch({ url: "/pages/mine/index" }),
  });
}

function submitOrder() {
  if (!selectedPlan.value) {
    uni.showToast({ title: "请选择会员方案", icon: "none" });
    return;
  }
  uni.showToast({
    title: `已选择${selectedPlan.value.name}，支付能力将在下一阶段接入`,
    icon: "none",
    duration: 2600,
  });
}

onMounted(loadData);
</script>

<template>
  <view class="member-page">
    <view class="navy-hero member-hero">
      <view class="safe-top" />
      <view class="member-nav-row">
        <view class="member-nav-button" @tap="goBack"><AppIcon name="arrow" :size="46" /></view>
        <text class="member-nav-title">会员中心</text>
        <view class="member-nav-placeholder" />
      </view>
      <view class="member-hero-icon"><AppIcon name="crown" :size="56" /></view>
      <text class="member-hero-title">让高质量研究持续复利</text>
      <text class="member-hero-subtitle">解锁深度专栏、直播回看、体系课程与核心研讨席位</text>
    </view>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" @retry="loadData" />

    <view v-else-if="data" class="member-content">
      <view class="surface-card current-member-card">
        <view class="current-member-top">
          <text class="current-member-label">当前会员</text>
          <view class="pill gold">有效中</view>
        </view>
        <text class="current-member-name"><AppIcon name="crown" :size="32" />{{ data.member.level_name }}</text>
        <text class="current-member-meta">{{ data.member.expire_date }} 到期 · {{ data.member.member_no }}</text>
      </view>

      <text class="member-section-title">当前已享权益</text>
      <view class="surface-card benefit-card">
        <view
          v-for="(benefit, index) in data.current_benefits"
          :key="benefit"
          class="benefit-row"
          :class="{ 'with-divider': index > 0 }"
        >
          <view class="benefit-check"><AppIcon name="check" :size="22" /></view>
          <text>{{ benefit }}</text>
        </view>
      </view>

      <text class="member-section-title">续费或升级</text>
      <view
        v-for="plan in data.plans"
        :key="plan.code"
        class="plan-card"
        :class="{ active: selectedPlanCode === plan.code }"
        @tap="selectedPlanCode = plan.code"
      >
        <view v-if="plan.recommended" class="recommend-badge">推荐</view>
        <view class="plan-radio"><AppIcon v-if="selectedPlanCode === plan.code" name="check" :size="22" /></view>
        <view class="plan-copy">
          <text class="plan-name">{{ plan.name }}</text>
          <text class="plan-period">{{ plan.period_label }}</text>
          <text class="plan-benefits">{{ plan.benefits.join(' · ') }}</text>
        </view>
        <view class="plan-price-copy">
          <text class="plan-price">¥{{ plan.price }}</text>
          <text v-if="plan.original_price" class="plan-original">¥{{ plan.original_price }}</text>
        </view>
      </view>

      <view class="member-agreement">
        确认开通即代表您同意会员服务协议。会员提供的是知识内容与投研交流服务，不承诺任何投资收益。
      </view>
    </view>

    <view v-if="data" class="member-bottom-bar">
      <view class="selected-price-copy">
        <text class="selected-price-label">应付金额</text>
        <text class="selected-price">¥{{ selectedPlan?.price || 0 }}</text>
      </view>
      <button class="member-pay-button" @tap="submitOrder">确认方案</button>
    </view>
  </view>
</template>

<style scoped lang="scss">
.member-page {
  min-height: 100vh;
  padding-bottom: calc(150rpx + env(safe-area-inset-bottom));
  background: #f4f6f9;
}

.member-hero {
  padding-bottom: 48rpx;
  text-align: center;
}

.member-nav-row,
.current-member-top,
.current-member-name,
.benefit-row,
.plan-card,
.member-bottom-bar {
  display: flex;
  align-items: center;
}

.member-nav-row,
.current-member-top {
  justify-content: space-between;
}

.member-nav-row {
  position: relative;
  z-index: 2;
  padding: 24rpx 30rpx 0;
}

.member-nav-button {
  display: flex;
  width: 68rpx;
  height: 68rpx;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
  transform: rotate(180deg);
}

.member-nav-title {
  color: rgba(255, 255, 255, 0.84);
  font-size: 25rpx;
  font-weight: 800;
}

.member-nav-placeholder {
  width: 68rpx;
}

.member-hero-icon {
  position: relative;
  z-index: 2;
  display: flex;
  width: 108rpx;
  height: 108rpx;
  margin: 36rpx auto 0;
  align-items: center;
  justify-content: center;
  border: 2rpx solid rgba(255, 218, 127, 0.55);
  border-radius: 34rpx;
  color: #ffe09a;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.1);
}

.member-hero-title,
.member-hero-subtitle,
.current-member-label,
.current-member-name,
.current-member-meta,
.member-section-title,
.plan-name,
.plan-period,
.plan-benefits,
.plan-price,
.plan-original,
.selected-price-label,
.selected-price {
  display: block;
}

.member-hero-title {
  position: relative;
  z-index: 2;
  margin-top: 22rpx;
  font-size: 38rpx;
  font-weight: 900;
}

.member-hero-subtitle {
  position: relative;
  z-index: 2;
  max-width: 590rpx;
  margin: 12rpx auto 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 23rpx;
  line-height: 1.66;
}

.member-content {
  padding: 24rpx 30rpx 42rpx;
}

.current-member-card {
  padding: 28rpx;
  border-color: #eed69f;
  background: linear-gradient(135deg, #fffaf0, #f7e4b7);
}

.current-member-label {
  color: #8d6a32;
  font-size: 20rpx;
  font-weight: 700;
}

.current-member-name {
  margin-top: 14rpx;
  gap: 10rpx;
  color: #4e3713;
  font-size: 31rpx;
  font-weight: 900;
}

.current-member-meta {
  margin-top: 8rpx;
  color: #8c734c;
  font-size: 20rpx;
}

.member-section-title {
  margin: 38rpx 2rpx 18rpx;
  color: #161b22;
  font-size: 30rpx;
  font-weight: 900;
}

.benefit-card {
  padding: 0 26rpx;
}

.benefit-row {
  min-height: 86rpx;
  gap: 16rpx;
  color: #26313c;
  font-size: 23rpx;
}

.benefit-row.with-divider {
  border-top: 1rpx solid #e5e9ed;
}

.benefit-check {
  display: flex;
  width: 42rpx;
  height: 42rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: #39b995;
}

.plan-card {
  position: relative;
  min-height: 160rpx;
  margin-top: 16rpx;
  padding: 24rpx;
  gap: 18rpx;
  border: 3rpx solid transparent;
  border-radius: 24rpx;
  background: #fff;
  box-shadow: 0 12rpx 28rpx rgba(4, 31, 55, 0.06);
}

.plan-card.active {
  border-color: #ffb229;
  background: #fffaf0;
}

.recommend-badge {
  position: absolute;
  top: 0;
  right: 0;
  padding: 7rpx 18rpx;
  border-radius: 0 21rpx 0 18rpx;
  color: #fff;
  background: #f17e1d;
  font-size: 18rpx;
  font-weight: 800;
}

.plan-radio {
  display: flex;
  width: 46rpx;
  height: 46rpx;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2rpx solid #cbd4db;
  border-radius: 50%;
  color: #fff;
  background: #fff;
}

.plan-card.active .plan-radio {
  border-color: #ffb229;
  background: #ffb229;
}

.plan-copy {
  min-width: 0;
  flex: 1;
}

.plan-name {
  font-size: 27rpx;
  font-weight: 900;
}

.plan-period {
  margin-top: 5rpx;
  color: #7b8490;
  font-size: 19rpx;
}

.plan-benefits {
  margin-top: 10rpx;
  color: #6d7984;
  font-size: 19rpx;
  line-height: 1.45;
}

.plan-price-copy {
  flex: 0 0 auto;
  text-align: right;
}

.plan-price {
  color: #d8781e;
  font-size: 31rpx;
  font-weight: 900;
}

.plan-original {
  margin-top: 4rpx;
  color: #a3abb2;
  font-size: 18rpx;
  text-decoration: line-through;
}

.member-agreement {
  margin-top: 26rpx;
  color: #858e98;
  font-size: 19rpx;
  line-height: 1.58;
  text-align: center;
}

.member-bottom-bar {
  position: fixed;
  z-index: 50;
  right: 0;
  bottom: 0;
  left: 0;
  padding: 16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  gap: 20rpx;
  border-top: 1rpx solid #e4e8ec;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 -10rpx 30rpx rgba(4, 31, 55, 0.08);
  backdrop-filter: blur(16px);
}

.selected-price-copy {
  min-width: 0;
  flex: 1;
}

.selected-price-label {
  color: #818a95;
  font-size: 18rpx;
}

.selected-price {
  margin-top: 3rpx;
  color: #df7b1c;
  font-size: 31rpx;
  font-weight: 900;
}

.member-pay-button {
  width: 246rpx;
  height: 82rpx;
  flex: 0 0 auto;
  border: none;
  border-radius: 44rpx;
  color: #fff;
  background: linear-gradient(135deg, #f4a621, #ed7425);
  font-size: 25rpx;
  font-weight: 900;
}
</style>
