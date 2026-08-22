import type { AcademyResponse, HomeResponse, ProfileResponse } from "@/types/portal";

const member = {
  id: 842,
  nickname: "Alex · 宏观价值派",
  level_name: "星球尊享年会员",
  expire_date: "2027-08-19",
  member_no: "NO. 00842",
  joined_days: 168,
  slogan: "在流动性周期与产业基本面中寻找确定性增长。",
};

export const mockHome: HomeResponse = {
  brand_name: "财不外露",
  brand_slogan: "学术财富与智慧的聚集地 · 私享投研智库",
  joined_count: 12840,
  member,
  pinned: [
    {
      id: 1,
      title: "新人必看 · 核心价值框架与投研指南",
      subtitle: "从零构建您的专业投研认知体系与底层逻辑",
      icon: "guide",
      accent: "orange",
    },
    {
      id: 2,
      title: "星球全景 · 投研体系分布与内容导航",
      subtitle: "涵盖基本面、宏观周期、量化工具与投教完整矩阵",
      icon: "compass",
      accent: "blue",
    },
    {
      id: 3,
      title: "「AI产业」全景剖析与投研脉络",
      subtitle: "理清算力、芯片、先进制程与大模型应用产业链机会",
      icon: "chip",
      accent: "cyan",
    },
  ],
  categories: ["全部", "交易追踪", "机构观点", "宏观市场"],
  feed: [
    {
      id: 1001,
      category: "交易追踪",
      content_type: "trade",
      title: "跟踪港美股重点个股动态，识别公司变化与阶段机会",
      summary:
        "深入分析近期市场波动背后的机构动向与大额期权异动，挖掘基本面优质资产的阶段性博弈机会。",
      published_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      access_level: "member",
      like_count: 156,
      comment_count: 28,
      author: { id: 1, name: "若琪", title: "投研主理人", avatar_text: "若" },
      liked_by_names: ["若琪", "志诚", "林海雪原", "QuantTrader"],
      comments: [
        {
          author: "林海雪原",
          avatar_text: "林",
          content: "港股科技龙头的估值修复逻辑很顺，观察南向资金连续净流入的节奏。",
        },
        {
          author: "QuantTrader",
          avatar_text: "Q",
          content: "注意关注今晚美股开盘后期权隐含波动率的变化，做好风控对冲。",
        },
      ],
    },
    {
      id: 1002,
      category: "机构调仓",
      content_type: "institution",
      title: "追踪头部机构调仓，观察市场偏好与行业配置方向",
      summary:
        "结合最新披露与资金流数据，拆解头部机构对科技、医疗和基础设施产业链的配置变化。",
      published_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      access_level: "member",
      like_count: 124,
      comment_count: 32,
      author: { id: 2, name: "马圳亿", title: "策略研究员", avatar_text: "马" },
      liked_by_names: ["Alex", "若琪", "宏观研究组"],
      comments: [],
    },
    {
      id: 1003,
      category: "宏观市场",
      content_type: "macro",
      title: "全球流动性拐点临近，如何理解利率与风险资产的再定价",
      summary:
        "从央行资产负债表、期限溢价和美元流动性三个维度观察市场定价的下一阶段。",
      published_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      access_level: "public",
      like_count: 98,
      comment_count: 17,
      author: { id: 3, name: "周远", title: "宏观研究员", avatar_text: "周" },
      liked_by_names: ["若琪", "Alex"],
      comments: [],
    },
  ],
};

export const mockAcademy: AcademyResponse = {
  live_sessions: [
    {
      id: 2001,
      schedule_text: "本周四 20:00 - 21:30",
      title: "全球宏观脉络与央行政策主线深度剖析",
      subtitle: "每周四固定宏观专场 · 梳理降息预期、流动性指标与各大类资产反应",
      access_label: "公开免费",
      tags: ["公开免费", "宏观讲解"],
      reservation_count: 864,
    },
    {
      id: 2002,
      schedule_text: "本周日 20:00 - 21:30",
      title: "重点个股深度研讨：科技龙头基本面变化",
      subtitle: "聚焦港美股科技龙头景气度与估值修复逻辑",
      access_label: "会员专享",
      tags: ["会员专享", "前沿科技"],
      reservation_count: 1420,
    },
  ],
  columns: [
    {
      id: 3001,
      status: "已完结 · 全12讲",
      title: "「AI产业」全景剖析",
      summary: "理清 AI 产业链结构与投资脉络，从底层硬件到应用全景。",
      article_count: 12,
      access_label: "会员免费",
      accent: "cyan",
    },
    {
      id: 3002,
      status: "连载中 · 已更9/18",
      title: "「AI趋势」前瞻解读",
      summary: "把握 AI 产业演进方向、关键节点和阶段性投资机会。",
      article_count: 9,
      access_label: "会员免费",
      accent: "orange",
    },
  ],
  course_categories: ["全部", "新手入门", "美股/技术", "期权衍生品"],
  courses: [
    {
      id: 4001,
      level: "入门",
      duration_hours: 3.5,
      lesson_count: 6,
      title: "港股打新公开课",
      summary: "零基础掌握港股打新全流程、中签机制与回拨风控策略。",
      tags: ["规则流程", "中签与回拨", "费用与风险", "破发防范"],
      price_label: "免费 / ¥99",
      badge: "热选",
      progress: 68,
    },
    {
      id: 4002,
      level: "进阶",
      duration_hours: 6,
      lesson_count: 10,
      title: "美股财报与估值实战",
      summary: "从财报结构、盈利质量到估值建模，形成可复用的公司研究框架。",
      tags: ["财报拆解", "估值模型", "案例实战"],
      price_label: "会员免费",
      badge: "进阶",
      progress: 20,
    },
  ],
};

export const mockProfile: ProfileResponse = {
  member,
  benefits: ["7大专栏畅读", "直播无限回看", "个股研讨专席"],
  stats: {
    learning_courses: 3,
    reading_columns: 7,
    replay_count: 18,
    learning_hours: 42.5,
  },
  recent_learning: {
    course_id: 4003,
    category: "交易实操",
    title: "港股打新与暗盘套利实战",
    lesson_title: "第 4 讲：暗盘套利原理与定价错配捕捉策略",
    learned_lessons: 5,
    total_lessons: 8,
    progress: 68,
    last_studied_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  },
  achievements: [
    { code: "hours-100", name: "百时研学者", icon: "fire", unlocked: true },
    { code: "cycle", name: "周期捕手", icon: "wave", unlocked: true },
    { code: "industry", name: "产业洞察家", icon: "chip", unlocked: true },
    { code: "leader", name: "智库领航者", icon: "crown", unlocked: false },
  ],
  assets: [
    { title: "我的研报笔记与批注", meta: "16 篇笔记", badge: "有更新", icon: "note" },
    { title: "离线下载与研报合集", meta: "3.2 GB", icon: "download" },
    { title: "我的收藏与重点关注", meta: "48 项关注", icon: "star" },
  ],
};
