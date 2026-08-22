<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";

onLaunch(() => {
  console.info("财不外露用户端启动");
});
</script>

<template>
  <slot />
</template>

<style lang="scss">
@import "./styles/theme.scss";
</style>
