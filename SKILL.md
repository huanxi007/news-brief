---
name: news-brief
description: 新闻简报 — 输入一个领域（财经/科技/AI人物/三地/大学艺术），把当天最重要的内容聚合成 5 条、每条约 200 字讲透，渲染成一流苹果大片风 PNG（朋友圈可发）。AI人物 模块有独立数据管线（X feed + web search + master_intel），其他模块走 RSS。自带信源配置与抓取/渲染脚本，本地隐私、零外部 key、本地 Opus 4.8 亲写。触发词：新闻简报、财经简报、今日财经、今日金融、看今天的新闻、科技简报、AI人物早报、AI人物动态、AI科技人物、一流人物洞察、三地大事、香港新闻、给孩子的新闻、大学艺术简报、daily brief、出一份简报、今日AI新闻。
---

# 新闻简报 · News Brief

**输入一个领域 → 当天最重要 5 条、每条约 200 字（发生什么→背景/数据→对你意味着什么）→ 一流苹果大片风 PNG（朋友圈可发）。**

引擎哲学：**引擎 = 对话 agent 本身**。由执行本 skill 的 Opus 4.8 亲自读素材、选要闻、写简报，脚本只负责抓取与渲染。零 API key、私密数据不出本地。

## 自带资产（self-contained）
本 skill 自带运行所需的一切，安装后无需额外配置：
- `scripts/news-brief.py` — RSS 抓取器（读自带 `config/rss-feeds.json`；AI人物 自动委托 ai-figure-fetch）
- `scripts/ai-figure-fetch.py` — AI人物 素材管线（x-feed → master_intel → JSON）
- `scripts/news-brief-render.py` — 渲染器（出一流暗色 PNG）
- `scripts/x-feed.py` — AI人物 X 动态聚合（拉 follow-builders 中心 feed，无需 cookie）
- `config/rss-feeds.json` — 自带信源配置（金融/三地/大学艺术）

> 脚本路径以本 skill 目录为准。下文用 `<SKILL>` 代表本 skill 安装目录（如 `~/.clacky/skills/news-brief`）。
> 依赖：`feedparser`、`requests`、`playwright`（已随龙虾环境就绪）。

## 领域别名
- 财经 / 金融 / 股市 → `金融`
- 科技 / AI / 人物 → `AI人物`
- 社会 / 三地 / 时事 → `三地`
- 大学 / 艺术 / 孩子 / 教育 → `大学艺术`

## 执行步骤（agent 照做）

### 通用模块（金融/三地/大学艺术）

1. **取素材**（带正文摘要的 JSON）：
   `python3 <SKILL>/scripts/news-brief.py <模块> --json --hours 48`

2. **你亲写**：从素材里选当天最重要的 **5 条**，每条写约 **200 字**——结构「发生了什么 → 关键背景/数据 → 对读者意味着什么」。要求：客观、信息密度高、不空话套话、**只用素材不编造**、**覆盖尽量多个不同来源**。
   **再写一段「朋友圈配文」**（见下方规范）——这是图文一起发的「文」，让人看完就想转发朋友圈。
   输出一个 JSON 对象存到 `~/JoyClaw/works/简报/<今日>/<模块>-stories.json`：
   ```json
   {
     "stories": [{"title":"精炼标题≤18字","source":"来源名","body":"约200字正文","ref":原文编号}],
     "caption": "朋友圈配文（120-200 字，欢喜口吻，详见规范）"
   }
   ```
   （用 Python `json.dump(..., ensure_ascii=False)` 写，避免引号转义出错。`stories` 必填，`caption` 强烈建议带上。）

### AI人物 模块（专属流程）

AI人物 与其他模块不同——素材来源是 X/Twitter 人物动态（非 RSS），需要三步数据采集。

**Step A — 取素材**：
```bash
python3 <SKILL>/scripts/ai-figure-fetch.py --hours 72
```
（自动先跑 x-feed.py 刷新 X 动态 → 入库 master_intel → 输出最近 72h 的 AI 人物推文 JSON）

**Step B — 补充网络搜索**（素材偏稀疏时必做）：
用 `web_search` 搜索 `"AI news today <日期>"` 和 `"Anthropic OpenAI AI news <月份> 2026"`，抓取 1-2 篇当日 AI 新闻聚合文章补充背景。

**Step C — 亲写 + 写 JSON**：
从素材 + 网络搜索结果中精选 5 条最重要动态（优先覆盖多个不同人物/公司），每条约 **200-300 字**。AI人物 简报的信息密度应高于通用模块——要有观点、有判断、有「所以呢」，不只是复述推文。
JSON 存到 `~/JoyClaw/works/简报/<今日>/AI人物-stories.json`，格式同上。`ref` 字段填素材编号（1-based）。

**Step D — 渲染出图**：
```bash
python3 <SKILL>/scripts/news-brief-render.py AI人物 --stories <json路径>
```

3. **渲染出图**（通用模块）：
   `python3 <SKILL>/scripts/news-brief-render.py <领域> --stories <json路径>`
   （AI人物 走 Step D：`python3 <SKILL>/scripts/news-brief-render.py AI人物 --stories <json路径>`）
   - **默认出苹果大片风**（1242 宽竖图，朋友圈点开字大）；加 `--style classic` 出旧版暗色编辑式。
   - 出 `新闻简报-<模块>.png`（图）+ `新闻简报-<模块>-朋友圈配文.txt`（文）。

4. **交付**：把 PNG **和** 朋友圈配文一起给用户——图发朋友圈，配文一键粘贴。一条龙「图文都备好，直接发」。

## 朋友圈配文规范（caption）
让简报从「摘要」升级成「可转发的朋友圈」。一段话，120-200 字，欢喜（Joey）口吻：
- **一句钩子开场**：今天市场/世界的「一句话定性」（如「今天就俩字：重排」），不要复述标题。
- **2-3 个要点**：每个配一个克制的 emoji 标记（🇯🇵/🚀/🍎 等，按内容选），口语、有判断、有温度，不是干巴巴的新闻条。
- **一句落点**：给读者一个「所以呢」——一个视角、一句提醒（如「别追情绪，看清结构」），落到普通人能用。
- **署名** `—— Joey`。
- **合规铁律**：禁荐股、禁报代码、禁收益承诺、禁「必涨/抄底」。只给视角与结构，不给操作指令。
- 不堆砌、不喊口号；像在跟朋友交个底，不像营销文案。

**AI人物 配文特别规范**：AI人物 的 caption 可以略长（200-350 字），5 个要点各配一个克制 emoji + 一句精炼判断，最后一句给出本周/当天的格局性判断（如「权力、金钱和真相，都在浮出水面」）。风格偏「技术人文」，像在跟同行聊趋势而非朋友圈喊话。

## 无人值守 / 定时模式
agent 不在场（cron 触发）时，跳过第 2 步，直接让脚本用本地 Opus / DeepSeek 自动出稿：
`python3 <SKILL>/scripts/news-brief-render.py 财经 --fallback`
（质量略低于 Opus 亲写，但全自动。约 140 字/条。需本地 joy_env 网关。）

## 信源（已验证）
| 领域 | 信源 |
|---|---|
| 金融 | 财联社 · 格隆汇 · 财新 · 华尔街见闻 · FT · WSJ · Bloomberg · CNBC |
| 三地 | 信报 · RTHK · 南华早报 ｜ 人民日报 · 中新网 ｜ BBC · 半岛 |
| 大学艺术 | 哈/耶/普/斯/麻 · 加州理工 · 剑桥 ｜ The Art Newspaper · ARTnews · Artsy · Hyperallergic · Colossal |
| AI人物 | follow-builders 精选 ~26 位一流 builder |

> 财联社/格隆汇/Bloomberg 经自托管 RSSHub——域名与密钥均不入库，运行时由环境变量 `RSSHUB_BASE` / `RSSHUB_KEY`（或本地 `~/JoyClaw/.rsshub-base` / `.rsshub-access-key` 文件）注入，未配置则自动跳过；财新/华尔街见闻/人民日报经 anyfeeder；耶鲁/斯坦福/信报经 Google News RSS。配置全在自带 `config/rss-feeds.json`。

## 设计语言
**默认 = 苹果大片风**（融合 first-class-poster-design 的 Apple 风，accent 换 Cartier 红 #C0202C）：
暗色首屏（领域 hairline 巨字 + 红晕 + mono kicker）→ 5 条新闻**明暗交替**段（Inter Tight 巨号 01–05 + mono 红源标签 chip + weight300 大标题 + 200 字正文，`*重点*`→红字强调）→ 暗色落款「欢喜龙虾. huanxi.ai」。1242px 宽，适配朋友圈/小红书。
- **模板填空式**：CSS 全锁死在 `news-brief-render.py` 的 `render_html_apple()`，LLM 只填 `{title,source,body}` 这套 JSON——**哪怕 DeepSeek 也出大片**（效果住模板里，不在模型脑子）。
- `--style classic`：旧版暗色卡片式（720 宽，头条红晕大卡 + 发丝分隔线）。

## 铁律
- **私密留本地**：只聚合公共信源，用户私密数据绝不上云。
- **数据锚定**：数字与事实只用素材原文，不估算、不编造。
- **来源必标**：每条标来源，链接进信源附录。
- **合规**：金融内容禁荐股、禁收益承诺。
