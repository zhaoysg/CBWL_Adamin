<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/http";
import { hasSession } from "@/utils/auth";
import AppIcon from "@/components/AppIcon.vue";

const form = reactive({ username: "", password: "" });
const loading = ref(false);
const captchaLoading = ref(false);
const captchaRequired = ref(true);
const captchaKey = ref("");
const sliderValue = ref(0);
const sliderVerified = ref(false);
const errorMessage = ref("");
const redirect = ref("/pages/mine/index");

const canSubmit = computed(
  () =>
    form.username.trim().length >= 2 &&
    form.password.length >= 6 &&
    (!captchaRequired.value || sliderVerified.value) &&
    !loading.value,
);

async function loadCaptcha() {
  captchaLoading.value = true;
  errorMessage.value = "";
  sliderValue.value = 0;
  sliderVerified.value = false;
  try {
    const result = await authApi.captcha();
    captchaRequired.value = result.enable;
    captchaKey.value = result.key;
    sliderVerified.value = !result.enable;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "验证码加载失败";
  } finally {
    captchaLoading.value = false;
  }
}

async function completeSlider(value: number) {
  sliderValue.value = value;
  if (!captchaRequired.value || sliderVerified.value || value < 95 || !captchaKey.value) return;
  captchaLoading.value = true;
  errorMessage.value = "";
  try {
    const result = await authApi.completeSlider(captchaKey.value);
    sliderVerified.value = result.verified;
    sliderValue.value = result.verified ? 100 : 0;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "滑块验证失败";
    await loadCaptcha();
  } finally {
    captchaLoading.value = false;
  }
}

async function submit() {
  if (!canSubmit.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    await authApi.login({
      username: form.username.trim(),
      password: form.password,
      captchaKey: captchaRequired.value ? captchaKey.value : undefined,
    });
    uni.showToast({ title: "登录成功", icon: "success" });
    setTimeout(() => uni.reLaunch({ url: redirect.value }), 250);
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error ? error.message : "登录失败";
    form.password = "";
    if (captchaRequired.value) await loadCaptcha();
  } finally {
    loading.value = false;
  }
}

function goBack() {
  uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/home/index" }) });
}

onLoad((options) => {
  const target = options?.redirect ? decodeURIComponent(String(options.redirect)) : "";
  if (target.startsWith("/pages/")) redirect.value = target;
});

onMounted(async () => {
  if (hasSession()) {
    uni.reLaunch({ url: redirect.value });
    return;
  }
  await loadCaptcha();
});
</script>

<template>
  <view class="login-page">
    <view class="login-hero">
      <button class="back-button" aria-label="返回" @tap="goBack">
        <AppIcon name="chevron-left" :size="28" />
      </button>
      <view class="brand-mark">财</view>
      <text class="brand-title">财不外露</text>
      <text class="brand-subtitle">登录后访问会员内容与个人权益</text>
    </view>

    <view class="login-card">
      <view class="field-group">
        <text class="field-label">账号</text>
        <input
          v-model="form.username"
          class="field-input"
          maxlength="32"
          autocomplete="username"
          placeholder="请输入用户名"
        />
      </view>
      <view class="field-group">
        <text class="field-label">密码</text>
        <input
          v-model="form.password"
          class="field-input"
          password
          maxlength="128"
          autocomplete="current-password"
          placeholder="请输入密码"
          confirm-type="done"
          @confirm="submit"
        />
      </view>

      <view v-if="captchaRequired" class="captcha-group">
        <view class="captcha-title-row">
          <text class="field-label">安全验证</text>
          <button class="refresh-captcha" :disabled="captchaLoading" @tap="loadCaptcha">刷新</button>
        </view>
        <view class="slider-shell" :class="{ 'slider-shell--verified': sliderVerified }">
          <slider
            :value="sliderValue"
            :disabled="captchaLoading || sliderVerified"
            :active-color="sliderVerified ? '#22a77a' : '#f2a12a'"
            background-color="#e8edf2"
            block-color="#ffffff"
            :block-size="30"
            :show-value="false"
            @change="completeSlider(Number($event.detail.value))"
          />
          <text class="slider-copy">{{ sliderVerified ? "验证完成" : "拖动滑块至最右侧" }}</text>
        </view>
      </view>

      <view v-if="errorMessage" class="error-box">{{ errorMessage }}</view>

      <button class="submit-button" :disabled="!canSubmit" :loading="loading" @tap="submit">
        {{ loading ? "正在登录…" : "登录" }}
      </button>
      <text class="security-copy">登录凭证仅用于本设备会话；退出登录后将清除本地凭证。</text>
    </view>
  </view>
</template>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  background: #f4f6f9;
}

.login-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: calc(var(--status-bar-height) + 70rpx) 40rpx 150rpx;
  color: #ffffff;
  background:
    radial-gradient(circle at 82% 18%, rgba(44, 101, 151, 0.38), transparent 36%),
    linear-gradient(145deg, #031a34, #062a4d 64%, #0b3b65);
}

.back-button {
  position: absolute;
  top: calc(var(--status-bar-height) + 24rpx);
  left: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72rpx;
  height: 72rpx;
  margin: 0;
  padding: 0;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.14);
  border-radius: 50%;
}

.back-button::after,
.refresh-captcha::after,
.submit-button::after {
  border: 0;
}

.brand-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 116rpx;
  height: 116rpx;
  color: #ffe37c;
  font-size: 58rpx;
  font-weight: 900;
  background: rgba(255, 178, 37, 0.12);
  border: 2rpx solid rgba(255, 181, 49, 0.65);
  border-radius: 30rpx;
}

.brand-title {
  margin-top: 25rpx;
  font-size: 42rpx;
  font-weight: 900;
}

.brand-subtitle {
  margin-top: 10rpx;
  color: rgba(255, 255, 255, 0.7);
  font-size: 23rpx;
}

.login-card {
  margin: -82rpx 30rpx 0;
  padding: 42rpx 32rpx 36rpx;
  background: #ffffff;
  border-radius: 28rpx;
  box-shadow: 0 18rpx 45rpx rgba(6, 35, 63, 0.12);
}

.field-group,
.captcha-group {
  margin-bottom: 28rpx;
}

.field-label {
  color: #1e2b38;
  font-size: 24rpx;
  font-weight: 800;
}

.field-input {
  height: 88rpx;
  margin-top: 12rpx;
  padding: 0 24rpx;
  color: #152331;
  font-size: 27rpx;
  background: #f6f8fa;
  border: 1rpx solid #e3e8ed;
  border-radius: 15rpx;
  box-sizing: border-box;
}

.captcha-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.refresh-captcha {
  margin: 0;
  padding: 5rpx 0;
  color: #175887;
  font-size: 21rpx;
  line-height: 1;
  background: transparent;
}

.slider-shell {
  position: relative;
  margin-top: 12rpx;
  padding: 8rpx 10rpx 30rpx;
  background: #f6f8fa;
  border: 1rpx solid #e3e8ed;
  border-radius: 15rpx;
}

.slider-shell--verified {
  background: #edf9f4;
  border-color: #a8dfca;
}

.slider-copy {
  position: absolute;
  right: 0;
  bottom: 10rpx;
  left: 0;
  color: #77838e;
  font-size: 20rpx;
  text-align: center;
}

.error-box {
  margin-bottom: 24rpx;
  padding: 18rpx 20rpx;
  color: #a8333b;
  font-size: 22rpx;
  line-height: 1.5;
  background: #fff1f2;
  border-radius: 12rpx;
}

.submit-button {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 90rpx;
  margin: 12rpx 0 0;
  color: #ffffff;
  font-size: 29rpx;
  font-weight: 900;
  background: linear-gradient(105deg, #0a4776, #092f55);
  border: 0;
  border-radius: 45rpx;
}

.submit-button[disabled] {
  color: rgba(255, 255, 255, 0.7);
  background: #9dabb7;
}

.security-copy {
  display: block;
  margin-top: 22rpx;
  color: #8a949d;
  font-size: 19rpx;
  line-height: 1.6;
  text-align: center;
}
</style>
