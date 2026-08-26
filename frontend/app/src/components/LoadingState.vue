<template>
  <view class="loading-state">
    <view class="spinner" />
    <text>正在加载投研内容…</text>
  </view>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  min-height: 420rpx;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  color: #798493;
  font-size: 26rpx;
}

.spinner {
  width: 54rpx;
  height: 54rpx;
  border: 6rpx solid rgba(7, 51, 94, 0.12);
  border-top-color: #ff9b20;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
