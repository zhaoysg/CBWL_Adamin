<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    name: string;
    size?: number;
  }>(),
  { size: 32 },
);

const glyphs: Record<string, string> = {
  home: "⌂",
  academy: "▥",
  mine: "●",
  search: "⌕",
  bell: "●",
  menu: "≡",
  arrow: "›",
  lock: "▣",
  guide: "▤",
  compass: "◈",
  chip: "▦",
  clock: "◷",
  play: "▶",
  book: "▥",
  crown: "♛",
  like: "♡",
  comment: "□",
  share: "↗",
  note: "▧",
  download: "↓",
  star: "★",
  fire: "♨",
  wave: "∿",
  leader: "♛",
  error: "!",
  retry: "↻",
  check: "✓",
};
</script>

<template>
  <text class="app-icon" :style="{ fontSize: `${props.size}rpx` }">{{ glyphs[props.name] || "•" }}</text>
</template>

<style scoped lang="scss">
.app-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: Arial, sans-serif;
  font-weight: 800;
  line-height: 1;
}
</style>
