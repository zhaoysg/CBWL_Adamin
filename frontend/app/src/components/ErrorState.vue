<script setup lang="ts">
import AppIcon from "./AppIcon.vue";

defineProps<{ message: string }>();
const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <view class="error-state">
    <view class="error-icon"><AppIcon name="error" :size="44" /></view>
    <text class="error-title">页面暂时没有加载成功</text>
    <text class="error-message">{{ message }}</text>
    <button class="retry-button" @tap="emit('retry')">
      <AppIcon name="retry" :size="28" />
      重新加载
    </button>
  </view>
</template>

<style scoped lang="scss">
.error-state {
  display: flex;
  min-height: 420rpx;
  padding: 48rpx;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.error-icon {
  display: flex;
  width: 76rpx;
  height: 76rpx;
  align-items: center;
  justify-content: center;
  border-radius: 24rpx;
  color: #b56c18;
  background: #fff1dd;
}

.error-title {
  margin-top: 24rpx;
  color: #151a22;
  font-size: 30rpx;
  font-weight: 800;
}

.error-message {
  margin-top: 12rpx;
  color: #7b8491;
  font-size: 24rpx;
  line-height: 1.6;
}

.retry-button {
  display: flex;
  height: 72rpx;
  margin-top: 28rpx;
  padding: 0 30rpx;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  border: none;
  border-radius: 38rpx;
  color: #fff;
  background: #07335e;
  font-size: 24rpx;
  font-weight: 800;
}
</style>
