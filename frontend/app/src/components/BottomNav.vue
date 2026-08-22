<script setup lang="ts">
import AppIcon from "./AppIcon.vue";

type NavKey = "home" | "academy" | "mine";

const props = defineProps<{ active: NavKey }>();

const navItems: Array<{ key: NavKey; label: string; path: string }> = [
  { key: "home", label: "首页", path: "/pages/home/index" },
  { key: "academy", label: "学院", path: "/pages/academy/index" },
  { key: "mine", label: "我的", path: "/pages/mine/index" },
];

function go(item: (typeof navItems)[number]) {
  if (item.key === props.active) return;
  uni.reLaunch({ url: item.path });
}
</script>

<template>
  <view class="bottom-nav-wrap">
    <view class="bottom-nav">
      <view
        v-for="item in navItems"
        :key="item.key"
        class="nav-item"
        :class="{ active: item.key === props.active }"
        @tap="go(item)"
      >
        <AppIcon :name="item.key" :size="48" />
        <text class="nav-label">{{ item.label }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped lang="scss">
.bottom-nav-wrap {
  position: fixed;
  z-index: 60;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  justify-content: center;
  padding: 0 28rpx calc(18rpx + env(safe-area-inset-bottom));
  pointer-events: none;
}

.bottom-nav {
  display: flex;
  width: min(620rpx, calc(100vw - 56rpx));
  height: 112rpx;
  padding: 8rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.88);
  border-radius: 62rpx;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 18rpx 48rpx rgba(8, 28, 51, 0.2);
  backdrop-filter: blur(20px);
  pointer-events: auto;
}

.nav-item {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
  border-radius: 54rpx;
  color: #11161f;
  transition: all 0.2s ease;

  &.active {
    color: #07335e;
    background: rgba(226, 230, 235, 0.82);
  }
}

.nav-label {
  font-size: 22rpx;
  font-weight: 800;
}
</style>
