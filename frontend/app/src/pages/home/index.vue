<script setup lang="ts">
import { onMounted, ref } from "vue";
import { portalApi } from "../../api/portal";

const data = ref<any>();
onMounted(async () => { data.value = await portalApi.home(); });
</script>

<template>
  <view v-if="data">
    <view class="hero">
      <view class="row"><view><view class="brand">财不外露 ✓</view><view class="subtitle">{{ data.brand_slogan }}</view></view><view class="badge">立即加入</view></view>
      <view class="subtitle">{{ data.joined_count.toLocaleString() }} 位专业投资人已加入</view>
    </view>
    <view class="card" v-for="item in data.pinned" :key="item.id">
      <view class="gold">置顶</view><view class="title">{{ item.title }}</view><view class="muted">{{ item.subtitle }}</view>
    </view>
    <view class="card" v-for="item in data.feed" :key="item.id">
      <view class="row"><view class="gold">#{{ item.category }}</view><view class="badge" v-if="item.access_level !== 'public'">仅限会员</view></view>
      <view class="title">{{ item.title }}</view><view class="muted">{{ item.summary }}</view>
      <view class="muted">♡ {{ item.like_count }}　▢ {{ item.comment_count }}　{{ item.author.title }}：{{ item.author.name }}</view>
    </view>
  </view>
</template>
