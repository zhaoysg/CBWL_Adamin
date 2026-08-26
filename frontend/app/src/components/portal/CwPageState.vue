<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean;
    error?: string;
    dark?: boolean;
  }>(),
  { loading: false, error: "", dark: false },
);

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <view v-if="loading || error" class="state" :class="{ 'state--dark': dark }">
    <view v-if="loading" class="state__loading">
      <view class="spinner" />
      <text>正在连接财不外露智库…</text>
    </view>
    <view v-else class="state__error">
      <text class="state__title">暂时无法获取内容</text>
      <text class="state__message">{{ error }}</text>
      <button class="retry" @tap="emit('retry')">重新加载</button>
    </view>
  </view>
</template>

<style scoped lang="scss">
.state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360rpx;
  padding: 60rpx 36rpx;
  color: #6f7b89;
  text-align: center;
}
.state--dark { color: rgba(255, 255, 255, 0.76); }
.state__loading,
.state__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22rpx;
}
.spinner {
  width: 54rpx;
  height: 54rpx;
  border: 5rpx solid rgba(19, 74, 123, 0.14);
  border-top-color: #ff9b21;
  border-radius: 50%;
  animation: spin 0.85s linear infinite;
}
.state__title { color: #14202c; font-size: 31rpx; font-weight: 800; }
.state--dark .state__title { color: #ffffff; }
.state__message { font-size: 24rpx; line-height: 1.6; }
.retry {
  min-width: 190rpx;
  margin: 4rpx 0 0;
  padding: 17rpx 28rpx;
  color: #ffffff;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 1;
  background: #082f57;
  border: 0;
  border-radius: 40rpx;
}
.retry::after { border: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
