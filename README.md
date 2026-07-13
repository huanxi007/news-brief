# 新闻简报 · News Brief

> 你的本地 AI 主编：输入一个领域，把当天最重要的新闻聚合成 5 条、每条约 200 字讲透，渲染成一张苹果大片风的简报长图（PNG），配好朋友圈文案，图文直接可发。

一个为 [Claude Code](https://claude.com/claude-code) / Agent 环境设计的**新闻聚合 Skill**。核心理念只有一句话：

**引擎 = 对话 Agent 本身。** 脚本只负责抓取与渲染，真正的「选题、判断、写作」由执行 Skill 的大模型亲自完成——这就是它和一切「RSS 摘要工具」的本质区别。

---

## 它解决什么问题

每天的信息太多、太碎、太杂。你想要的不是更多链接，而是——

**「今天，我这个领域，最该知道的几件事，以及它们到底意味着什么。」**

新闻简报只做这一件事：

- **每条约 200 字讲透**：结构固定为「发生了什么 → 关键背景/数据 → 对你意味着什么」，不是标题党、不是流水账，是一个懂行主编的判断。
- **只用素材、不编造**：数字与事实全部锚定在抓取的原文上，每条标注来源。
- **一张图 + 一段文案**：产出 1242px 宽的竖版简报图（朋友圈点开字够大）和一段 120–200 字的朋友圈配文，图文一起发。
- **本地隐私、零外部 key**：只聚合公共信源，不需要任何付费 API；私有数据不出本地。

## 四个频道

| 你说 | 频道 | 信源 |
|---|---|---|
| 财经 / 金融 / 股市 | `金融` | 财联社 · 格隆汇 · 财新 · 华尔街见闻 · FT · WSJ · Bloomberg · CNBC |
| 科技 / AI / 人物 | `AI人物` | X 上约 26 位一流 AI builder 的当日动态（follow-builders 精选） |
| 社会 / 三地 / 时事 | `三地` | 信报 · RTHK · 南华早报 ｜ 人民日报 · 中新网 ｜ BBC · 半岛 |
| 大学 / 艺术 / 教育 | `大学艺术` | 哈/耶/普/斯/麻 · 加州理工 · 剑桥 ｜ The Art Newspaper · ARTnews · Artsy · Hyperallergic · Colossal |

所有信源均已逐个实测可抓，配置集中在 `config/rss-feeds.json`，可自由增删。

## 工作原理

```
┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐
│ 1. 抓取      │ → │ 2. Agent 亲写     │ → │ 3. 渲染          │
│ news-brief.py│   │ 选 5 条 · 每条    │   │ news-brief-      │
│ RSS → JSON   │   │ ~200字 · 写配文   │   │ render.py → PNG  │
└─────────────┘   └──────────────────┘   └─────────────────┘
```

1. **抓取**（脚本）：`news-brief.py` 并发抓取该频道全部 RSS 源，按时间窗口（默认 36h）过滤、去重、限量，输出带正文摘要的 JSON。新闻读完即弃，不写入任何知识库。
2. **写作**（Agent）：执行 Skill 的大模型从素材池中精选当天最重要的 5 条，每条写约 200 字 + 一段朋友圈配文，存成一个 `stories.json`。要求覆盖尽量多个不同来源、只用素材不编造。
3. **渲染**（脚本）：`news-brief-render.py` 把 `stories.json` 填入锁死的 HTML/CSS 模板，用 Playwright 截图出 PNG。

### 关键设计：模板填空式渲染

版式 CSS 全部锁死在渲染脚本的 `render_html_apple()` 里，LLM 只负责填 `{title, source, body}` 这套 JSON——**效果住在模板里，不在模型脑子里**。哪怕换成小模型供稿，出图质量也不掉。

### 设计语言

默认「苹果大片风」：暗色首屏（领域 hairline 巨字 + 红晕 + mono kicker）→ 5 条新闻明暗交替段（Inter Tight 巨号编号 01–05 + 红色来源标签 chip + 大标题 + 200 字正文，`*重点*` 自动转红字强调）→ 暗色落款。1242px 宽，适配朋友圈/小红书。加 `--style classic` 可切旧版暗色编辑式卡片。

## 仓库结构

```
news-brief/
├── SKILL.md                      # Skill 定义（Agent 的执行手册）
├── README.md                     # 本文
├── config/
│   └── rss-feeds.json            # 全部信源配置（金融/三地/大学艺术）
└── scripts/
    ├── news-brief.py             # RSS 抓取器（并发抓取 → 分组 JSON）
    ├── news-brief-render.py      # 渲染器（stories.json → 苹果大片风 PNG）
    ├── ai-figure-fetch.py        # AI人物 素材管线（X feed → SQLite → JSON）
    ├── x-feed.py                 # X 动态聚合（拉中心化 feed，无需 cookie）
    └── finance_brief_gen.py      # 无人值守财经快报（可选，DeepSeek/模板兜底）
```

## 安装

### 作为 Claude Code Skill

```bash
git clone https://github.com/huanxi007/news-brief.git ~/.claude/skills/news-brief
```

依赖三个 Python 包（渲染需要 Chromium）：

```bash
pip install feedparser requests playwright
playwright install chromium
```

装好后对 Claude 说「**出一份财经简报**」「**今天的科技简报**」「**给孩子的大学艺术简报**」即可。

### 脚本独立使用（不依赖 Agent）

```bash
# 看看今天金融频道抓到了什么
python3 scripts/news-brief.py 金融 --json --hours 48

# 用自己写好的 stories.json 渲染出图
python3 scripts/news-brief-render.py 金融 --stories /path/to/stories.json
```

## 配置

### stories.json 格式（Agent 或人工供稿）

```json
{
  "stories": [
    {
      "title": "精炼标题（≤18字）",
      "source": "来源名",
      "body": "约200字正文，*星号包裹* 的内容渲染为红字强调",
      "ref": 1
    }
  ],
  "caption": "朋友圈配文（120–200 字）"
}
```

### 自托管 RSSHub（可选）

财联社 / 格隆汇 / Bloomberg 三个源走自托管 [RSSHub](https://docs.rsshub.app/)。出于安全考虑，实例域名与访问密钥**均不写入仓库**，运行时注入：

| 变量 | 含义 | 本地回退文件 |
|---|---|---|
| `RSSHUB_BASE` | RSSHub 实例地址（如 `https://rsshub.example.com`） | `~/JoyClaw/.rsshub-base` |
| `RSSHUB_KEY` | 实例 ACCESS_KEY | `~/JoyClaw/.rsshub-access-key` |

**不配置也能用**：这几个源会自动跳过，FT / WSJ / CNBC / 财新 / 华尔街见闻等公共源照常工作。

### 增删信源

直接编辑 `config/rss-feeds.json`，每个源只需 `name` + `url` 两个字段。`pending_sources` 段记录了调研过但暂无公开订阅的源，供后来者参考。

## AI人物 频道（独立管线）

这个频道的素材来自 X/Twitter 而非 RSS：

1. `x-feed.py` 拉取 [follow-builders](https://github.com/zarazhangrui/follow-builders) 的中心化 feed（该仓库每日刷新约 26 位一流 AI builder 的推文），**无需 X 账号、无需 cookie**，一次 HTTP 即可。
2. 推文入库本地 SQLite（`master_intel` 表）做去重与积累。
3. `ai-figure-fetch.py` 输出最近 72h 素材 JSON，Agent 结合网络搜索补充背景后写作——这个频道要求信息密度更高：有观点、有判断、有「所以呢」，不只是复述推文。

## 无人值守模式

Agent 不在场（如 cron 定时触发）时，跳过亲写环节，由脚本调用本地 LLM 网关自动出稿：

```bash
python3 scripts/news-brief-render.py 财经 --fallback
```

`finance_brief_gen.py` 则是一条更彻底的确定性管线：抓取 → DeepSeek 撰写 → 落档 Markdown，DeepSeek 不通时自动降级为模板直出，**内容生成永不空手**（适合每天 07:00 的定时推送）。

## 铁律

- **私密留本地**：只聚合公共信源，用户私密数据绝不上云。
- **数据锚定**：数字与事实只用素材原文，不估算、不编造。
- **来源必标**：每条标注来源，可回溯原文。
- **合规**：金融内容禁荐股、禁报代码、禁收益承诺——只给视角与结构，不给操作指令。

## 谁最需要

- 每天要发朋友圈立专业人设的**金融 / 保险从业者**
- 见客户前要谈资、要信息差的**专业人士**
- 想给孩子启发、晚饭有的聊的**家长**
- 追 AI 前沿、要跟住一流人物的**创业者**

---

*欢喜龙虾 · huanxi.ai —— 本地隐私，云端聚合，每天替你把世界读一遍。*
