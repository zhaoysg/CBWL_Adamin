<script setup lang="ts">
import { onMounted, ref } from "vue";
import { portalApi } from "../../api/portal";

const data = ref<any>();
onMounted(async () => { data.value = await portalApi.academy(); });
</script>

<template>
  <view v-if="data">
    <view class="hero"><view class="brand">投研学院</view><view class="subtitle">10 门体系精品课 · 7 大深度专栏 · 专题研讨直播</view></view>
    <view class="card"><view class="title">专题直播研讨</view></view>
    <view class="card" v-for="item in data.live_sessions" :key="item.id">
      <view class="row"><view class="badge">{{ item.schedule_text }}</view><view class="badge">{{ item.access_label }}</view></view>
      <view class="title">{{ item.title }}</view><view class="muted">{{ item.subtitle }}</view><view class="muted">{{ item.reservation_count }} 人已预约</view>
    </view>
    <view class="card"><view class="title">星球深度图文专栏</view></view>
    <view class="card" v-for="item in data.columns" :key="item.id"><view class="gold">{{ item.status }}</view><view class="title">{{ item.title }}</view><view class="muted">{{ item.summary }}</view></view>
    <view class="card"><view class="title">体系化精品课</view></view>
    <view class="card" v-for="item in data.courses" :key="item.id"><view class="row"><view class="badge">{{ item.level }}</view><view class="gold">{{ item.price_label }}</view></view><view class="title">{{ item.title }}</view><view class="muted">{{ item.summary }}</view></view>
  </view>
</template>
