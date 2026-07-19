# 新闻简报 skill · 欢喜龙虾安装说明

## 装
把 `news-brief` 文件夹整个放进 `~/.clacky/skills/`：

```bash
mv news-brief ~/.clacky/skills/
```

依赖三个 Python 包（渲染需要 Chromium，龙虾环境通常已就绪）：

```bash
pip install feedparser requests playwright && playwright install chromium
```

## 用
对龙虾说一句即可：

> 「出一份财经简报」 / 「今天的 AI 人物早报」 / 「三地大事」 / 「给孩子的大学艺术简报」

几十秒后，一张 1242px 苹果大片风简报图 + 一段朋友圈配文落桌面，图文直接可发。

## 可选配置（不配也能用）
财联社 / 格隆汇 / Bloomberg 三个源走自托管 RSSHub。在 `~/.clacky/joy_profile.yml` 里加两行即可启用：

```yaml
rsshub_base: https://你的rsshub实例地址
rsshub_key: 你的ACCESS_KEY
```

不配置时这三个源自动跳过，FT / WSJ / CNBC / 财新 / 华尔街见闻等公共源照常工作。

## 适配说明（2026-07-19 龙虾版）
- RSSHub 域名与密钥零硬编码，注入链：环境变量 → joy_profile.yml → 本地文件
- AI人物 频道的 joy.db 经 `joy_env.db_path()` 统一解析，表缺失自动建，新用户开箱即用
- 新老用户路径自适应：有 `~/JoyClaw` 走老路径，没有走 `~/.clacky/joy_data`，再不行落桌面
- 本地隐私：新闻读完即弃，零外部 API key

—— 欢喜龙虾 · huanxi.ai
