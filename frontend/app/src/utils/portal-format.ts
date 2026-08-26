export function formatCount(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (value >= 10000) {
    const amount = value / 10000;
    return `${amount >= 10 ? amount.toFixed(1) : amount.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}万`;
  }
  return value.toLocaleString("zh-CN");
}

export function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "刚刚";
  const delta = Math.max(0, Date.now() - timestamp);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (delta < minute) return "刚刚";
  if (delta < hour) return `${Math.floor(delta / minute)} 分钟前`;
  if (delta < day) return `${Math.floor(delta / hour)} 小时前`;
  if (delta < 7 * day) return `${Math.floor(delta / day)} 天前`;
  const date = new Date(timestamp);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

export function formatHours(value: number): string {
  if (!Number.isFinite(value)) return "0";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function accessLabel(level: string): string {
  const labels: Record<string, string> = {
    public: "公开阅读",
    login: "登录可见",
    member: "仅限会员",
    premium: "尊享会员",
  };
  return labels[level] || "会员内容";
}
