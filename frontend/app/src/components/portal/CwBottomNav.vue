<script setup lang="ts">
import CwIcon from "./CwIcon.vue";

type NavKey = "home" | "academy" | "mine";

const props = defineProps<{ active: NavKey }>();

const items: Array<{ key: NavKey; label: string; icon: string; path: string }> = [
  { key: "home", label: "首页", icon: "home", path: "/pages/home/index" },
  { key: "academy", label: "学院", icon: "academy", path: "/pages/academy/index" },
  { key: "mine", label: "我的", icon: "mine", path: "/pages/mine/index" },
];

function go(item: (typeof items)[number]) {
  if (item.key === props.active) return;
  uni.switchTab({
    url: item.path,
    fail: () => uni.reLaunch({ url: item.path }),
  });
}
</script>

<template>
  <view class="bottom-nav-shell" :style="{ paddingBottom: 'max(18rpx, env(safe-area-inset-bottom))' }">
    <view class="bottom-nav">
      <button
        v-for="item in items"
        :key="item.key"
        class="nav-item"
        :class="{ 'nav-item--active': item.key === props.active }"
        hover-class="nav-item--hover"
        @tap="go(item)"
      >
        <view class="nav-icon-wrap">
          <CwIcon :name="item.icon" :size="45" :tone="item.key === props.active ? 'navy' : 'muted'" />
        </view>
        <text>{{ item.label }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped lang="scss">
.bottom-nav-shell {
  position: fixed;
  z-index: 100;
  right: 0;
  bottom: 0;
  left: 0;
  pointer-events: none;
}
.bottom-nav {
  display: flex;
  align-items: stretch;
  width: 560rpx;
  min-height: 112rpx;
  margin: 0 auto;
  padding: 8rpx;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.94);
  border: 1rpx solid rgba(8, 47, 87, 0.08);
  border-radius: 60rpx;
  box-shadow: 0 20rpx 50rpx rgba(6, 35, 65, 0.18);
  backdrop-filter: blur(24rpx);
  pointer-events: auto;
}
.nav-item {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3rpx;
  min-width: 0;
  margin: 0;
  padding: 10rpx 8rpx;
  color: #111820;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 1.2;
  background: transparent;
  border: 0;
  border-radius: 50rpx;
}
.nav-item::after { border: 0; }
.nav-item--active {
  color: #072e54;
  background: linear-gradient(145deg, #edf1f5, #ffffff);
  box-shadow: inset 0 0 0 1rpx rgba(7, 46, 84, 0.04);
}
.nav-item--hover { opacity: 0.72; }
.nav-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 50rpx;
}
</style>
