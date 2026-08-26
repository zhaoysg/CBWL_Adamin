<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    name: string;
    size?: number;
    tone?: "navy" | "gold" | "orange" | "cyan" | "green" | "muted" | "white";
  }>(),
  { size: 28, tone: "navy" },
);

const glyphs: Record<string, string> = {
  home: "⌂",
  academy: "▥",
  mine: "●",
  search: "⌕",
  bell: "●",
  menu: "≡",
  crown: "♛",
  guide: "▤",
  compass: "◆",
  chip: "▦",
  like: "♡",
  comment: "□",
  lock: "▣",
  live: "▶",
  book: "▥",
  clock: "◷",
  arrow: "›",
  settings: "⚙",
  note: "▤",
  download: "↓",
  star: "★",
  fire: "●",
  wave: "⌁",
  play: "▶",
  check: "✓",
  close: "×",
};
</script>

<template>
  <text
    class="cw-icon"
    :class="`cw-icon--${props.tone}`"
    :style="{ fontSize: `${props.size}rpx`, width: `${props.size * 1.25}rpx`, height: `${props.size * 1.25}rpx` }"
    aria-hidden="true"
  >{{ glyphs[props.name] || "•" }}</text>
</template>

<style scoped lang="scss">
.cw-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-family: Arial, sans-serif;
  font-weight: 900;
  line-height: 1;
}
.cw-icon--navy { color: #082f57; }
.cw-icon--gold { color: #f4b422; }
.cw-icon--orange { color: #ff8a20; }
.cw-icon--cyan { color: #21afca; }
.cw-icon--green { color: #23a687; }
.cw-icon--muted { color: #8b96a3; }
.cw-icon--white { color: #ffffff; }
</style>
