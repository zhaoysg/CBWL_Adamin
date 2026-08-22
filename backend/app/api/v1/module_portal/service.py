from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal

from .schema import (
    AcademyResponse,
    Achievement,
    AssetEntry,
    Author,
    ColumnCard,
    CommentPreview,
    ContentDetailResponse,
    ContentSection,
    CourseCard,
    CourseChapter,
    CourseDetailResponse,
    FeedItem,
    HomeResponse,
    LearningStats,
    LessonSummary,
    LiveSession,
    MemberCenterResponse,
    MemberPlan,
    MemberSummary,
    PinnedItem,
    ProfileResponse,
    RecentLearning,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 22, hour, minute, tzinfo=timezone.utc)


MEMBER = MemberSummary(
    id=842,
    nickname="Alex · 宏观价值派",
    level_name="星球尊享年会员",
    expire_date=date(2027, 8, 19),
    member_no="NO. 00842",
    joined_days=168,
    slogan="在流动性周期与产业基本面中寻找确定性增长。",
)


class PortalService:
    """M1 deterministic acceptance read model.

    This provider is blocked by default in production. M2 replaces it with a
    SQLAlchemy repository while preserving the validated response contracts.
    """

    @staticmethod
    def home() -> HomeResponse:
        return HomeResponse(
            brand_name="财不外露",
            brand_slogan="学术财富与智慧的聚集地 · 私享投研智库",
            joined_count=12840,
            member=deepcopy(MEMBER),
            pinned=[
                PinnedItem(
                    id=1,
                    title="新人必看 · 核心价值框架与投研指南",
                    subtitle="从零构建您的专业投研认知体系与底层逻辑",
                    icon="guide",
                    accent="orange",
                    target_type="content",
                    target_id=1001,
                ),
                PinnedItem(
                    id=2,
                    title="星球全景 · 投研体系分布与内容导航",
                    subtitle="涵盖基本面、宏观周期、量化工具与投教完整矩阵",
                    icon="compass",
                    accent="blue",
                    target_type="academy",
                ),
                PinnedItem(
                    id=3,
                    title="「AI产业」全景剖析与投研脉络",
                    subtitle="理清算力、芯片、先进制程与大模型应用产业链机会",
                    icon="chip",
                    accent="cyan",
                    target_type="content",
                    target_id=1003,
                ),
            ],
            categories=["全部", "交易追踪", "机构观点", "宏观市场"],
            feed=[
                FeedItem(
                    id=1001,
                    category="交易追踪",
                    content_type="trade",
                    title="跟踪港美股重点个股动态，识别公司变化与阶段机会",
                    summary="深入分析近期市场波动背后的机构动向与大额期权异动，挖掘基本面优质资产的阶段性博弈机会。",
                    published_at=_dt(14, 45),
                    access_level="member",
                    like_count=156,
                    comment_count=28,
                    author=Author(id=1, name="若琪", title="投研主理人", avatar_text="若"),
                    liked_by_names=["若琪", "志诚", "林海雪原", "QuantTrader"],
                    comments=[
                        CommentPreview(
                            author="林海雪原",
                            avatar_text="林",
                            content="港股科技龙头的估值修复逻辑很顺，观察南向资金连续净流入的节奏。",
                        ),
                        CommentPreview(
                            author="QuantTrader",
                            avatar_text="Q",
                            content="注意关注今晚美股开盘后期权隐含波动率的变化，做好风控对冲。",
                        ),
                    ],
                ),
                FeedItem(
                    id=1002,
                    category="机构观点",
                    content_type="institution",
                    title="追踪头部机构调仓，观察市场偏好与行业配置方向",
                    summary="结合最新披露与资金流数据，拆解头部机构对科技、医疗和基础设施产业链的配置变化。",
                    published_at=_dt(12, 55),
                    access_level="member",
                    like_count=124,
                    comment_count=32,
                    author=Author(id=2, name="马圳亿", title="策略研究员", avatar_text="马"),
                    liked_by_names=["马圳亿", "若琪"],
                ),
                FeedItem(
                    id=1003,
                    category="宏观市场",
                    content_type="macro",
                    title="降息预期再定价：流动性拐点如何传导至权益与黄金",
                    summary="从政策利率、美元流动性和实际利率三个维度，梳理未来一个季度大类资产的核心观察框架。",
                    published_at=_dt(9, 20),
                    access_level="public",
                    like_count=98,
                    comment_count=17,
                    author=Author(id=3, name="方恒", title="宏观研究员", avatar_text="方"),
                    liked_by_names=["宏观观察", "Cathy"],
                ),
            ],
        )

    @staticmethod
    def academy() -> AcademyResponse:
        return AcademyResponse(
            live_sessions=[
                LiveSession(
                    id=2001,
                    schedule_text="本周四 20:00 - 21:30",
                    title="全球宏观脉络与央行政策主线深度剖析",
                    subtitle="梳理降息预期、流动性指标与各大类资产反应",
                    access_label="公开免费",
                    tags=["公开免费", "宏观讲解"],
                    reservation_count=864,
                ),
                LiveSession(
                    id=2002,
                    schedule_text="本周日 20:00 - 21:30",
                    title="重点个股深度研讨：科技龙头基本面变化",
                    subtitle="聚焦港美股科技龙头景气度与估值修复逻辑",
                    access_label="会员专享",
                    tags=["会员专享", "前沿科技"],
                    reservation_count=1420,
                ),
            ],
            columns=[
                ColumnCard(
                    id=3001,
                    status="已完结 · 全12讲",
                    title="「AI产业」全景剖析",
                    summary="理清 AI 产业链结构与投资脉络，从底层硬件到应用全景。",
                    article_count=12,
                    access_label="会员免费",
                    accent="cyan",
                ),
                ColumnCard(
                    id=3002,
                    status="连载中 · 已更9/18",
                    title="「AI趋势」前瞻解读",
                    summary="把握 AI 产业演进方向、关键节点和阶段性投资机会。",
                    article_count=9,
                    access_label="会员免费",
                    accent="orange",
                ),
            ],
            course_categories=["全部", "新手入门", "美股/技术", "期权衍生品"],
            courses=[
                CourseCard(
                    id=4001,
                    category="新手入门",
                    level="入门",
                    duration_hours=3.5,
                    lesson_count=6,
                    title="港股打新公开课",
                    summary="零基础掌握港股打新全流程、中签机制与回拨风控策略。",
                    tags=["规则流程", "中签与回拨", "费用与风险", "破发防范"],
                    price_label="免费",
                    badge="热选",
                    progress=68,
                ),
                CourseCard(
                    id=4002,
                    category="美股/技术",
                    level="进阶",
                    duration_hours=6.0,
                    lesson_count=10,
                    title="美股财报与估值实战",
                    summary="从财报结构、盈利质量到估值建模，形成可复用的公司研究框架。",
                    tags=["财报拆解", "估值模型", "案例实战"],
                    price_label="会员免费",
                    progress=20,
                ),
                CourseCard(
                    id=4003,
                    category="期权衍生品",
                    level="进阶",
                    duration_hours=5.2,
                    lesson_count=8,
                    title="港股打新与暗盘套利实战",
                    summary="从定价、回拨到暗盘交易，建立可执行的机会筛选与风险控制清单。",
                    tags=["交易实操", "暗盘机制", "风险控制"],
                    price_label="会员免费",
                    badge="实战",
                    progress=68,
                ),
            ],
        )

    @staticmethod
    def profile() -> ProfileResponse:
        return ProfileResponse(
            member=deepcopy(MEMBER),
            benefits=["7大专栏畅读", "直播无限回看", "个股研讨专席"],
            stats=LearningStats(
                learning_courses=3,
                reading_columns=7,
                replay_count=18,
                learning_hours=42.5,
            ),
            recent_learning=RecentLearning(
                course_id=4003,
                category="交易实操",
                title="港股打新与暗盘套利实战",
                lesson_title="第 4 讲：暗盘套利原理与定价错配捕捉策略",
                learned_lessons=5,
                total_lessons=8,
                progress=68,
                last_studied_at=_dt(13, 30),
            ),
            achievements=[
                Achievement(code="hours-100", name="百时研学者", icon="fire", unlocked=True),
                Achievement(code="cycle", name="周期捕手", icon="wave", unlocked=True),
                Achievement(code="industry", name="产业洞察家", icon="chip", unlocked=True),
                Achievement(code="leader", name="智库领航者", icon="crown", unlocked=False),
            ],
            assets=[
                AssetEntry(title="我的研报笔记与批注", meta="16 篇笔记", badge="有更新", icon="note"),
                AssetEntry(title="离线下载与研报合集", meta="3.2 GB", icon="download"),
                AssetEntry(title="我的收藏与重点关注", meta="48 项关注", icon="star"),
            ],
        )

    @staticmethod
    def content_detail(content_id: int) -> ContentDetailResponse | None:
        feed_item = next((item for item in PortalService.home().feed if item.id == content_id), None)
        if feed_item is None:
            return None
        return ContentDetailResponse(
            id=feed_item.id,
            category=feed_item.category,
            title=feed_item.title,
            summary=feed_item.summary,
            published_at=feed_item.published_at,
            access_level=feed_item.access_level,
            like_count=feed_item.like_count,
            comment_count=feed_item.comment_count,
            reading_minutes=8,
            author=feed_item.author,
            sections=[
                ContentSection(
                    heading="核心观察",
                    paragraphs=[
                        "近期价格波动并不只来自单一事件，而是资金偏好、盈利预期和衍生品仓位共同作用的结果。判断阶段机会时，需要把价格变化放回公司基本面和流动性环境中验证。",
                        "我们重点观察盈利预期是否持续上修、机构持仓是否形成共识，以及成交结构是否出现由短线博弈向中期配置切换的迹象。",
                    ],
                ),
                ContentSection(
                    heading="跟踪框架",
                    paragraphs=[
                        "第一步确认产业与公司层面的真实变化；第二步观察估值是否已经充分反映；第三步通过仓位、期权隐含波动率和资金流判断交易拥挤度。",
                        "当基本面改善、估值仍有空间且交易结构不过度拥挤时，才具备更高质量的阶段性研究价值。",
                    ],
                ),
            ],
        )

    @staticmethod
    def course_detail(course_id: int) -> CourseDetailResponse | None:
        course = next((item for item in PortalService.academy().courses if item.id == course_id), None)
        if course is None:
            return None
        return CourseDetailResponse(
            id=course.id,
            category=course.category,
            level=course.level,
            duration_hours=course.duration_hours,
            lesson_count=course.lesson_count,
            title=course.title,
            summary=course.summary,
            price_label=course.price_label,
            progress=course.progress,
            student_count=2680,
            highlights=["建立完整研究流程", "掌握关键风险节点", "形成可复用分析模板", "结合真实案例实践"],
            chapters=[
                CourseChapter(
                    id=1,
                    title="第一章 · 建立基础框架",
                    lessons=[
                        LessonSummary(id=1, title="课程导论与研究目标", duration_minutes=18, is_preview=True, learned=True),
                        LessonSummary(id=2, title="核心规则与参与机制", duration_minutes=32, learned=True),
                        LessonSummary(id=3, title="信息收集与标的筛选", duration_minutes=36, learned=course.progress >= 45),
                    ],
                ),
                CourseChapter(
                    id=2,
                    title="第二章 · 风险与实战",
                    lessons=[
                        LessonSummary(id=4, title="定价、回拨与暗盘机制", duration_minutes=41, learned=course.progress >= 60),
                        LessonSummary(id=5, title="仓位控制与破发防范", duration_minutes=38, learned=course.progress >= 80),
                        LessonSummary(id=6, title="案例复盘与执行清单", duration_minutes=34, learned=course.progress >= 100),
                    ],
                ),
            ],
        )

    @staticmethod
    def member_center() -> MemberCenterResponse:
        return MemberCenterResponse(
            member=deepcopy(MEMBER),
            current_benefits=[
                "7 大深度专栏畅读",
                "全部会员直播无限回看",
                "体系课程会员价",
                "核心研讨专属席位",
                "研报合集与离线下载",
            ],
            plans=[
                MemberPlan(
                    code="month",
                    name="月度会员",
                    period_label="连续 30 天",
                    price=Decimal("99.00"),
                    original_price=Decimal("129.00"),
                    benefits=["会员专栏", "直播回看"],
                ),
                MemberPlan(
                    code="year",
                    name="星球尊享年会员",
                    period_label="连续 365 天",
                    price=Decimal("899.00"),
                    original_price=Decimal("1188.00"),
                    benefits=["全部专栏", "全部直播", "研讨专席"],
                    recommended=True,
                ),
            ],
        )
