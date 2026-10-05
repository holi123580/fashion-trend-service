# Fashion Trend Service - 全球时尚趋势采集与分析服务

为电子衣柜提供实时全球时尚趋势数据，包括最新穿搭图、热门博主、杂志资讯和AI搭配灵感。

## 技术栈

- **后端框架**: FastAPI (Python 3.10+)
- **ORM**: SQLAlchemy 2.0
- **数据库**: SQLite (默认) / 可切换 PostgreSQL/MySQL
- **采集**: RSS (feedparser) + Apify Actor + httpx
- **缓存**: 内存缓存 (TTL 5分钟)
- **定时任务**: APScheduler (默认每60分钟自动采集)

## 快速开始

### 1. 安装依赖

```bash
cd fashion-trend-service
pip install -r requirements.txt
```

### 2. 配置环境变量 (可选)

创建 `.env` 文件：

```env
# 数据库 (默认SQLite，无需配置)
# DATABASE_URL=postgresql://user:pass@localhost/fashion_trends

# Apify Token (用于Apify Actor采集，可选)
APIFY_TOKEN=your_apify_token_here

# AI API (用于AI搭配灵感生成，可选；不配置则使用本地规则算法)
AI_API_KEY=your_ai_api_key
AI_API_BASE=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# 服务配置
API_HOST=0.0.0.0
API_PORT=8000
REFRESH_INTERVAL_MINUTES=60
```

### 3. 启动服务

```bash
python main.py
```

服务启动后访问：
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 4. 首次采集

服务启动时会自动初始化默认RSS数据源。手动触发采集：

```bash
curl -X POST http://localhost:8000/api/trends/refresh \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

或在电子衣柜前端"全球趋势"页面点击右上角"刷新趋势"按钮。

## API 端点

### 趋势数据

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/trends/refresh` | 手动触发采集 |
| GET | `/api/trends/outfits` | 获取搭配列表 |
| GET | `/api/trends/signals` | 获取趋势信号(热度计算) |

#### GET /api/trends/outfits 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| region | string | global | 地区: global/us/uk/jp/kr/cn/eu |
| sort | string | likes | 排序: followers/likes/sales/heat |
| days | int | 7 | 时间窗口(天) |
| style | string | - | 风格标签筛选 |
| limit | int | 20 | 每页数量 |
| offset | int | 0 | 偏移量 |

### 博主

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/creators` | 获取博主列表 |

#### GET /api/creators 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| platform | string | - | 平台: wear/musinsa/instagram/youtube/tiktok/lemon8 |
| sort | string | followers | 排序: followers/likes |
| limit | int | 20 | 每页数量 |

### 杂志资讯

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/magazines/latest` | 获取最新杂志文章 |
| GET | `/api/magazines/sources` | 获取可用杂志来源列表 |

### AI搭配灵感

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/ai/styling-inspiration` | 生成AI搭配灵感 |

#### POST /api/ai/styling-inspiration 请求体

```json
{
  "wardrobe_items": [
    {"name": "黑色西装", "category": "outer", "color": "黑色", "season": "spring"}
  ],
  "region": "global",
  "style": "minimalist",
  "occasion": "日常",
  "season": "spring"
}
```

## 数据源配置

### RSS源 (默认启用，无需API Key)

已预设以下RSS源：
- Vogue US / UK / Japan
- Hypebeast
- WWD (Women's Wear Daily)
- Business of Fashion
- Highsnobiety
- Fashionista
- The Fashion Law
- WEAR News (日本)

添加自定义RSS源：直接在数据库 `sources` 表中插入记录，或修改 `adapters/rss.py` 中的 `PRESET_RSS_FEEDS`。

### Apify Actor (需要APIFY_TOKEN)

支持以下Apify Actor（需在Apify平台订阅对应Actor）：
- Lemon8 Scraper
- WEAR (ZOZO) Fashion Coordinate Scraper
- Musinsa Scraper
- Website Image Downloader

配置：设置环境变量 `APIFY_TOKEN`，并在数据库 `sources` 表中添加 `type='apify'` 的来源。

### 自建爬虫 (高级)

在 `adapters/` 目录下新建适配器，继承 `BaseAdapter` 并实现 `fetch()` 方法。使用 Playwright 或 Scrapy，必须：
- 遵守 robots.txt
- 设置合理的请求间隔 (至少1秒)
- 配置 User-Agent
- 实现重试机制 (最多3次)
- 不绕过登录墙、验证码、付费墙

## 排序与热度算法

### 排序方式

1. **按粉丝量**: `creator.followers` 降序
2. **按点赞量**: `post.likes` / `outfit.likes` 降序
3. **按销售量**: 电商平台销售排名/评论数综合 (需电商平台接入)
4. **综合热度**: 加权计算

### 综合热度公式

```
heat_score = 0.4 * 点赞归一化 + 0.3 * 粉丝归一化 + 0.2 * 销量归一化 + 0.1 * 时间新鲜度
```

- 点赞归一化: 当前点赞数 / 最大点赞数
- 粉丝归一化: 相关创作者粉丝数 / 最大粉丝数
- 销量归一化: 销售量 / 最大销售量 (电商平台接入后生效)
- 时间新鲜度: 1.0 (7天内)，随时间递减

## 数据库模型

### 7张核心表

1. **Source** - 数据来源 (名称、类型、URL、地区、语言)
2. **Creator** - 博主/创作者 (平台、用户名、粉丝数、地区、风格标签)
3. **Post** - 帖子 (标题、摘要、图片URL、原文链接、点赞/收藏/评论)
4. **Outfit** - 搭配方案 (搭配图片、品牌、风格标签、季节、地区)
5. **OutfitItem** - 搭配单品 (名称、品牌、类目、颜色、购买链接)
6. **TrendSignal** - 趋势信号 (热度分、粉丝量、点赞量、销售量)
7. **MagazineArticle** - 杂志文章 (杂志名、标题、摘要、封面图、原文链接)

### WardrobeItem 字段扩展

前端电子衣柜的衣物数据模型已包含：
- `tags` - 风格标签
- `category` - 一级品类
- `subCategory` - 二级品类
- `color` - 颜色
- `brand` - 品牌 (可扩展)
- `season` - 适穿季节

## AI工具定义

注册到电子衣柜AI助手的5个工具：

1. `get_trending_outfits(region, days, style, sort_by, limit)` - 获取热门搭配
2. `get_top_creators(platform, sort_by, limit)` - 获取热门博主
3. `get_latest_magazine_content(source, limit)` - 获取杂志资讯
4. `match_wardrobe_with_trends(wardrobeItemIds, region, style)` - 衣柜匹配趋势
5. `refresh_trends(sources)` - 触发数据采集

## AI系统提示词

```
你是电子衣柜的全球时尚趋势助手。用户询问最新穿搭、博主、杂志或搭配灵感时，必须调用工具获取实时数据，不得编造。回答必须标注来源、日期、粉丝/点赞/销量依据。生成灵感时，结合用户衣柜已有单品，输出 3 套方案，每套包含：趋势来源、适合场景、用我衣柜里哪些单品复刻、还缺什么单品、可替换品牌。只使用工具返回的图片链接和摘要，不复制完整版权内容。
```

## 前端集成

电子衣柜前端已集成"全球趋势"类目，包含4个子标签：

1. **最新穿搭图** - 展示全球热门搭配，支持地区/排序/时间筛选
2. **最热博主** - 展示时尚博主排行榜，支持平台筛选
3. **杂志资讯** - 展示最新时尚杂志文章
4. **AI搭配灵感** - 基于趋势+用户衣柜生成3套搭配方案

前端API地址配置：在浏览器控制台执行 `localStorage.setItem('trends_api_base', 'http://your-server:8000')`

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_trends.py::TestModels -v
```

测试覆盖：
- 数据库模型 CRUD
- RSS/Apify 适配器初始化
- 趋势服务缓存
- 排序算法 (粉丝/点赞/地区筛选)
- AI搭配灵感生成 (本地规则算法)
- 衣柜单品匹配

## 合规底线

**严格遵守以下规则：**

1. **不绕过登录墙、验证码、付费墙** - 只采集公开可访问的内容
2. **遵守 robots.txt** - 采集前检查目标网站 robots.txt
3. **遵守平台 ToS** - 使用官方API/RSS优先，第三方采集器需确认合规
4. **只存元数据** - 只存储图片URL、原文链接、标题、摘要、作者、互动数据
5. **不存储完整版权文章** - 摘要截断到300字符
6. **不二次分发高清原图** - 只存储图片URL，不下载存储原图
7. **商业使用前必须获得授权** - 本服务仅供个人学习和研究使用
8. **所有AI生成内容必须标注来源和日期**

## 定时任务

服务启动后自动每60分钟执行一次采集（可通过 `REFRESH_INTERVAL_MINUTES` 配置）。

也可以使用系统级定时任务：

```bash
# Linux crontab
*/30 * * * * curl -X POST http://localhost:8000/api/trends/refresh -H "Content-Type: application/json" -d '{}'

# Windows Task Scheduler
# 创建任务，每30分钟执行: curl -X POST http://localhost:8000/api/trends/refresh
```

## 部署

### 本地开发

```bash
python main.py --reload
```

### 生产部署 (Gunicorn + Uvicorn Worker)

```bash
pip install gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (示例)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

## 项目结构

```
fashion-trend-service/
├── main.py                 # FastAPI入口
├── config.py               # 配置管理
├── database.py             # 数据库连接
├── models.py               # SQLAlchemy模型 (7张表)
├── schemas.py              # Pydantic Schema
├── requirements.txt        # Python依赖
├── README.md               # 本文档
├── .env.example            # 环境变量示例
├── adapters/               # 采集适配器
│   ├── __init__.py
│   ├── base.py             # 适配器基类
│   ├── rss.py              # RSS适配器 (Vogue/Hypebeast等)
│   └── apify.py            # Apify适配器
├── services/               # 业务逻辑
│   ├── __init__.py
│   ├── trend_service.py    # 趋势服务 (采集/排序/缓存/热度)
│   └── ai_service.py       # AI服务 (搭配灵感生成)
├── routers/                # API路由
│   ├── __init__.py
│   ├── trends.py           # 趋势API
│   ├── creators.py         # 博主API
│   ├── magazines.py        # 杂志API
│   └── ai.py               # AI搭配API
└── tests/                  # 测试
    └── test_trends.py      # 综合测试
```

## 常见问题

**Q: 为什么采集不到数据？**
A: 检查：1) 网络连接 2) RSS源是否可用 3) 是否被目标网站封禁IP 4) Apify Token是否正确配置

**Q: 如何添加新的数据源？**
A: 1) RSS源：在 `adapters/rss.py` 的 `PRESET_RSS_FEEDS` 添加 2) Apify：在 `adapters/apify.py` 添加 3) 自建爬虫：继承 `BaseAdapter` 实现 `fetch()`

**Q: AI搭配灵感不准确怎么办？**
A: 配置 `AI_API_KEY` 使用外部AI模型；不配置时使用本地规则算法，效果有限。

**Q: 数据库存满了怎么办？**
A: 1) 定期清理旧数据 2) 切换到PostgreSQL 3) 只保留最近30天数据

## License

仅供个人学习和研究使用。商业使用前请获得相关数据来源的授权。
