<script setup lang="ts">
import { onMounted, ref } from "vue";
import { portalApi } from "../../api/portal";

const data = ref<any>();
onMounted(async () => { data.value = await portalApi.profile(); });
</script>

<template>
  <view v-if="data">
    <view class="hero"><view class="brand">个人中心</view><view class="title">{{ data.member.nickname }} ✓</view><view class="subtitle">{{ data.member.slogan }}</view><view class="subtitle">{{ data.member.member_no }} · 同行 {{ data.member.joined_days }} 天</view></view>
    <view class="card"><view class="row"><view class="title">♛ {{ data.member.level_name }}</view><view class="gold">{{ data.member.expire_date }} 到期</view></view><view class="muted">{{ data.benefits.join(' · ') }}</view></view>
    <view class="card"><view class="title">研学数据</view><view class="muted">{{ data.stats.learning_courses }} 门在学课程 · {{ data.stats.reading_columns }} 个专栏 · {{ data.stats.replay_count }} 期回看 · {{ data.stats.learning_hours }}h</view></view>
    <view class="card"><view class="title">最近在学</view><view class="gold">{{ data.recent_learning.category }}</view><view class="title">{{ data.recent_learning.title }}</view><view class="muted">{{ data.recent_learning.lesson_title }} · 进度 {{ data.recent_learning.progress }}%</view></view>
    <view class="card"><view class="title">投研成就勋章</view><view class="muted" v-for="item in data.achievements" :key="item.code">{{ item.unlocked ? '✓' : '○' }} {{ item.name }}</view></view>
    <view class="card"><view class="title">投研资产与记录</view><view class="muted" v-for="item in data.assets" :key="item.title">{{ item.title }}　{{ item.meta }}</view></view>
  </view>
</template>
