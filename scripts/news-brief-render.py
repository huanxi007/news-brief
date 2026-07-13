#!/usr/bin/env python3
"""
新闻简报渲染器 (News Brief renderer) — 把简报内容排成一流暗色编辑式 PNG。
用法：
  python3 news-brief-render.py 财经 --stories <json路径>   # agent(本地 Opus 4.8) 亲写供稿
  python3 news-brief-render.py 财经                         # 让脚本 LLM 自动出稿（需 joy_env 本地 Opus）
  python3 news-brief-render.py 金融 --fallback              # 本地 Opus 未起时用 DeepSeek
领域别名：财经/金融→金融 · 科技/AI/人物→AI人物 · 社会/三地→三地 · 大学/艺术/孩子→大学艺术
"""
import sys, os, json, re, subprocess, asyncio
from pathlib import Path
from datetime import datetime

# ── 路径自解析：自带优先，缺省退回 ~/JoyClaw ──
SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
JC = Path.home() / "JoyClaw"
BRIEF = SCRIPTS / "news-brief.py"
DB = (JC / "joy.db") if (JC / "joy.db").exists() else (SKILL / "data" / "joy.db")
OUT_ROOT = (JC / "works" / "简报") if JC.exists() else (Path.home() / "Desktop" / "news-brief")
OUT = OUT_ROOT / datetime.now().strftime("%Y-%m-%d")

ARGS = sys.argv[1:]
FALLBACK = "--fallback" in ARGS or "--deepseek" in ARGS
ALIAS = {"财经": "金融", "金融": "金融", "股市": "金融",
         "科技": "AI人物", "ai": "AI人物", "AI": "AI人物", "人物": "AI人物",
         "社会": "三地", "三地": "三地", "时事": "三地",
         "大学": "大学艺术", "艺术": "大学艺术", "孩子": "大学艺术", "教育": "大学艺术"}
RAW = next((a for a in ARGS if not a.startswith("--")), "财经")
def _resolve(raw):
    if raw in ALIAS: return ALIAS[raw]
    if raw.lower() in ALIAS: return ALIAS[raw.lower()]
    for k, v in ALIAS.items():            # 子串匹配：「大学艺术」含「大学」
        if k in raw or raw in k: return v
    return "金融"
MODULE = _resolve(RAW)
STORIES_FILE = ARGS[ARGS.index("--stories") + 1] if "--stories" in ARGS else None
TITLE_CN = {"金融": "财经", "三地": "三地大事", "大学艺术": "大学 · 艺术", "AI人物": "AI 科技人物"}[MODULE]
# 苹果风首屏巨字（短而有力，hairline 巨号用）
HERO_WORD = {"金融": "财经", "三地": "三地", "大学艺术": "大学<b>·</b>艺术", "AI人物": "AI<b>·</b>人物"}[MODULE]
# 渲染风格：apple（默认·苹果大片）/ classic（旧暗色编辑式）
STYLE = (ARGS[ARGS.index("--style") + 1] if "--style" in ARGS else "apple").lower()


# ── LLM（仅在脚本自动出稿模式需要；agent 亲写 --stories 模式不依赖）──
def llm(prompt, system):
    sys.path.insert(0, os.path.expanduser("~/.clacky/lib"))
    if FALLBACK:
        try:
            for line in open(JC / ".env"):
                if line.startswith("DEEPSEEK_API_KEY="):
                    os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
    else:
        os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        import joy_env
    except Exception:
        sys.exit("✗ 未找到本地 LLM 网关 joy_env；请用 --stories 由 agent 亲写供稿。")
    if FALLBACK:
        return joy_env.llm(prompt, system=system, max_tokens=2600, prefer_model="claude-opus-4-6")
    for m in joy_env._models():
        if m.get("model") == "claude-opus-4-6":
            return joy_env._post_openai(joy_env._chat_url(m["base_url"]), m.get("api_key", ""),
                                        m["model"], prompt, system, 0.7, 2600, _raise=True)
    return None


def get_items():
    if MODULE == "AI人物":
        import sqlite3
        con = sqlite3.connect(DB)
        rows = con.execute(
            "SELECT m.name, m.title, COALESCE(NULLIF(i.summary,''), i.content), i.url "
            "FROM master_intel i JOIN masters m ON m.id=i.master_id "
            "WHERE date(i.created_at)>=date('now','-2 day') ORDER BY i.id DESC LIMIT 40").fetchall()
        con.close()
        return [{"source": n, "title": (t or "")[:30], "summary": (c or "")[:300],
                 "link": u or "", "region": ""} for n, t, c, u in rows]
    r = subprocess.run([sys.executable, str(BRIEF), MODULE, "--json", "--hours", "48"],
                       capture_output=True, text=True)
    data = json.loads(r.stdout).get(MODULE, {})
    flat = []
    for sub, items in data.items():
        for it in items:
            flat.append({**it, "region": "" if sub == "_" else sub})
    return flat[:20]


SYS = ("你是欢喜的资深新闻主编，眼光毒辣、文字老练。只用给定材料，绝不编造事实或数字。")

def build_prompt(items):
    src = "\n".join(
        f"[{n}] 【{i['source']}】{i.get('region','')} {i['title']}\n    摘要：{i.get('summary','')[:240]}"
        for n, i in enumerate(items, 1))
    return (f"今日「{TITLE_CN}」要闻（含摘要）：\n{src}\n\n"
            "任务：选出当天最重要的【5 条】，每条写一段**约 200 字**的简报，结构：发生了什么 → "
            "关键背景或数据 → 对读者意味着什么。客观、信息密度高、不空话套话。"
            "覆盖尽量多个不同来源。只用上面材料。\n"
            "严格输出 JSON 数组（5 个元素），每个：{\"title\":\"精炼标题≤18字\",\"source\":\"来源名\","
            "\"body\":\"约200字正文\",\"ref\":原文编号}。只输出 JSON，不要任何额外文字。\n"
            "★ 铁律：正文/标题里若要加引号，一律用中文「」或『』，绝不用英文双引号 \"，"
            "否则会破坏 JSON。")


def parse_json(txt):
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    i, j = txt.find("["), txt.rfind("]")
    blob = txt[i:j + 1] if (i >= 0 and j > i) else txt
    try:
        return json.loads(blob)
    except Exception:
        pass
    # 容错：DeepSeek 常在正文里夹未转义英文双引号→按固定 schema 逐对象正则抽取
    stories = []
    for m in re.finditer(r"\{(.*?)\}", blob, re.S):
        obj = m.group(1)
        def grab(key, nxt):
            mm = re.search(rf'"{key}"\s*:\s*"(.*?)"\s*(?:,\s*"{nxt}"|,?\s*$)', obj, re.S)
            return mm.group(1).strip().replace('\\"', '"') if mm else ""
        title, source, body = grab("title", "source"), grab("source", "body"), grab("body", "ref")
        rm = re.search(r'"ref"\s*:\s*(\d+)', obj)
        if title and body:
            stories.append({"title": title, "source": source, "body": body,
                            "ref": int(rm.group(1)) if rm else len(stories) + 1})
    if not stories:
        raise ValueError("LLM 输出无法解析为简报 JSON")
    return stories


# ── 强调标记：*重点* → 主 accent 粗体（自动 nowrap，避免数字/术语被折断）──
def emph(s):
    if not s: return ""
    return re.sub(r"\*(.+?)\*", r"<b>\1</b>", str(s))


# ── 苹果大片风版式（默认）· 模板填空式：CSS 锁死，LLM 只填 {title,source,body} ──
#    设计 token 取自 first-class-poster-design 的 Apple 风，accent 换成欢喜龙虾 Cartier 红。
def render_html_apple(stories, items):
    link_by_ref = {n: i.get("link", "") for n, i in enumerate(items, 1)}
    today = datetime.now()
    nsrc = len(set(i["source"] for i in items))
    secs = []
    for idx, s in enumerate(stories, 1):
        link = link_by_ref.get(s.get("ref"), "")
        lead = " lead" if idx == 1 else ""
        tone = "light" if idx % 2 == 1 else "dark"   # 明暗交替（首条 light）
        more = f'<a class="smore" href="{link}">原文 ↗</a>' if link else ""
        secs.append(f"""
      <section class="story {tone}{lead}"><div class="in">
        <div class="shead"><div class="snum">{idx:02d}</div>
          <div class="smid"><span class="schip">{s['source']}</span>{more}</div></div>
        <h2 class="stitle">{emph(s['title'])}</h2>
        <p class="sbody">{emph(s['body'])}</p>
      </div></section>""")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@200;300;400;500&family=Noto+Sans+SC:wght@200;300;400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root{{--accent:#C0202C;--ad:#EC5560;
 --sans:'Noto Sans SC','Inter Tight',sans-serif;--tight:'Inter Tight','Noto Sans SC',sans-serif;--mono:'JetBrains Mono',monospace}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#F5F5F7;font-family:var(--sans);-webkit-font-smoothing:antialiased}}
.brief{{width:1242px;margin:0 auto;background:#F5F5F7;overflow:hidden}}
.in{{position:relative;z-index:2}}
/* —— 暗色首屏 —— */
.mast{{position:relative;background:#0D0D0F;color:#FAFAF8;padding:130px 104px 108px;overflow:hidden}}
.mast::before{{content:'';position:absolute;inset:0;pointer-events:none;
 background:radial-gradient(ellipse 60% 42% at 84% 6%,rgba(192,32,44,.24),transparent 60%)}}
.kick{{font-family:var(--mono);font-size:23px;letter-spacing:.30em;color:var(--ad);text-transform:uppercase}}
.hero{{margin-top:42px;font-family:var(--tight);font-weight:200;font-size:200px;line-height:.84;
 letter-spacing:-.045em;color:#FAFAF8}}
.hero b{{color:var(--ad);font-weight:200;font-size:.5em;vertical-align:.18em;padding:0 .06em}}
.metarow{{margin-top:58px;font-family:var(--mono);font-size:25px;letter-spacing:.04em;color:#a6a6ac;
 display:flex;gap:32px;flex-wrap:wrap}}
.metarow b{{color:#FAFAF8;font-weight:500}}
/* —— 新闻段（明暗交替）—— */
.story{{padding:96px 104px;position:relative}}
.story.light{{background:#F5F5F7;color:#1d1d1f}}
.story.dark{{background:#0D0D0F;color:#FAFAF8}}
.story.dark::before{{content:'';position:absolute;inset:0;pointer-events:none;
 background:radial-gradient(ellipse 54% 40% at 86% 10%,rgba(236,85,96,.10),transparent 62%)}}
.shead{{display:flex;align-items:flex-start;gap:34px;margin-bottom:36px}}
.snum{{font-family:var(--tight);font-weight:200;font-size:132px;line-height:.78;letter-spacing:-.05em;flex:none}}
.story.light .snum{{color:#c7c7cc}}.story.dark .snum{{color:#33333a}}
.lead .snum{{color:var(--accent)}}
.smid{{flex:1;padding-top:18px}}
.schip{{display:inline-block;font-family:var(--mono);font-size:21px;letter-spacing:.02em;
 border-radius:8px;padding:6px 16px}}
.story.light .schip{{color:var(--accent);border:1px solid rgba(192,32,44,.40);background:rgba(192,32,44,.06)}}
.story.dark .schip{{color:var(--ad);border:1px solid rgba(236,85,96,.42);background:rgba(236,85,96,.09)}}
.smore{{font-family:var(--mono);font-size:20px;text-decoration:none;margin-left:18px;color:#9a9aa0}}
.stitle{{font-size:56px;font-weight:300;line-height:1.26;letter-spacing:-.018em;max-width:1034px}}
.story.light .stitle{{color:#1d1d1f}}.story.dark .stitle{{color:#FAFAF8}}
.stitle b{{font-weight:500;color:var(--accent);white-space:nowrap}}.story.dark .stitle b{{color:var(--ad)}}
.sbody{{margin-top:36px;font-size:30px;font-weight:300;line-height:1.76;max-width:1034px}}
.story.light .sbody{{color:#46464b}}.story.dark .sbody{{color:#a6a6ac}}
.sbody b{{font-weight:500}}.story.light .sbody b{{color:#1d1d1f}}.story.dark .sbody b{{color:#FAFAF8}}
.lead .stitle{{font-size:82px;font-weight:300;line-height:1.16}}
.lead .sbody{{font-size:34px}}.lead.light .sbody{{color:#3a3a3f}}
/* —— 暗色落款 —— */
.foot{{background:#0D0D0F;color:#6a6a72;padding:88px 104px;display:flex;align-items:flex-end;
 justify-content:space-between;gap:40px;font-family:var(--mono);font-size:23px;line-height:1.7}}
.foot .brand{{font-family:var(--tight);font-weight:300;font-size:42px;color:#FAFAF8;letter-spacing:-.01em}}
.foot .brand b{{color:var(--ad);font-weight:400}}
.foot .r{{text-align:right;white-space:nowrap}}
</style></head><body><div class="brief">
  <section class="mast"><div class="in">
    <div class="kick">新闻简报 · {MODULE}</div>
    <div class="hero">{HERO_WORD}</div>
    <div class="metarow"><span><b>{today:%Y.%m.%d}</b> 周{'一二三四五六日'[today.weekday()]}</span>
      <span>今日精选 <b>{len(stories)}</b> 条</span><span>聚合 <b>{nsrc}</b> 信源</span></div>
  </div></section>
  {''.join(secs)}
  <section class="foot"><span class="brand">欢喜龙虾<b>.</b> huanxi.ai</span>
    <span class="r">本地隐私 · 云端聚合<br>每日 07:00 · {TITLE_CN}</span></section>
</div></body></html>"""


# ── 一流版式 HTML（classic 暗色编辑式，旧版保留）──
def render_html(stories, items):
    link_by_ref = {n: i.get("link", "") for n, i in enumerate(items, 1)}
    today = datetime.now()
    cards = []
    for idx, s in enumerate(stories, 1):
        link = link_by_ref.get(s.get("ref"), "")
        lead = "lead" if idx == 1 else ""
        more = f'<a class="more" href="{link}">原文 ↗</a>' if link else ""
        cards.append(f"""
        <article class="story {lead}">
          <div class="sn">{idx:02d}</div>
          <div class="sc">
            <div class="srow"><span class="chip">{s['source']}</span>{more}</div>
            <h2>{s['title']}</h2>
            <p>{s['body']}</p>
          </div>
        </article>""")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<style>
:root{{--bg:#08080A;--t1:#F4F4F6;--t2:#A2A2AC;--t3:#56565F;--line:rgba(255,255,255,.07);
--red:#C0202C;--reds:#EC5560;--sans:-apple-system,"PingFang SC",Inter,system-ui,sans-serif;
--mono:"SF Mono",ui-monospace,"JetBrains Mono",monospace;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);font-family:var(--sans);-webkit-font-smoothing:antialiased;
display:flex;justify-content:center;padding:46px 0}}
.page{{width:720px;background:var(--bg);border:1px solid var(--line);border-radius:24px;overflow:hidden}}
.mast{{padding:56px 56px 40px;border-bottom:1px solid var(--line);
background:radial-gradient(130% 130% at 90% -20%,rgba(192,32,44,.20),transparent 52%)}}
.kick{{font-family:var(--mono);font-size:11px;letter-spacing:.34em;color:var(--reds);text-transform:uppercase}}
.big{{font-size:72px;font-weight:850;letter-spacing:-.03em;color:var(--t1);line-height:.96;margin:20px 0 8px}}
.big em{{color:var(--red);font-style:normal}}
.sub{{font-family:var(--mono);font-size:12.5px;color:var(--t2);margin-top:16px;display:flex;gap:16px;flex-wrap:wrap}}
.sub b{{color:var(--t1)}}
.feed{{padding:8px 56px 20px}}
.story{{display:flex;gap:22px;padding:34px 0;border-bottom:1px solid var(--line)}}
.story:last-child{{border-bottom:none}}
.sn{{font-family:var(--mono);font-size:15px;color:var(--t3);width:30px;flex:none;padding-top:6px}}
.sc{{flex:1}}
.srow{{display:flex;align-items:center;gap:12px;margin-bottom:12px}}
.chip{{font-family:var(--mono);font-size:11px;letter-spacing:.03em;color:var(--reds);
border:1px solid rgba(192,32,44,.42);background:rgba(192,32,44,.08);border-radius:6px;padding:3px 9px}}
.more{{font-family:var(--mono);font-size:11px;color:var(--t3);text-decoration:none;margin-left:auto}}
.story h2{{font-size:21px;font-weight:700;color:var(--t1);line-height:1.32;letter-spacing:-.01em}}
.story p{{font-size:14.5px;color:var(--t2);line-height:1.85;margin-top:12px}}
.lead h2{{font-size:30px;line-height:1.22}}
.lead p{{font-size:15.5px;color:#C8C8D0}}
.lead{{background:linear-gradient(180deg,rgba(192,32,44,.05),transparent);
margin:0 -20px;padding:34px 20px;border-radius:14px;border-bottom:1px solid var(--line)}}
.foot{{padding:30px 56px 44px;border-top:1px solid var(--line);display:flex;
justify-content:space-between;font-family:var(--mono);font-size:11px;color:var(--t3);letter-spacing:.05em}}
.foot b{{color:var(--t1)}}.foot span em{{color:var(--red);font-style:normal}}
</style></head><body><div class="page">
  <div class="mast">
    <div class="kick">新闻简报 · NEWS BRIEF</div>
    <div class="big">{TITLE_CN}<em>.</em></div>
    <div class="sub"><span><b>{today:%Y.%m.%d}</b> 周{'一二三四五六日'[today.weekday()]}</span>
      <span>今日精选 <b>{len(stories)}</b> 条</span><span>聚合 <b>{len(set(i['source'] for i in items))}</b> 信源</span></div>
  </div>
  <div class="feed">{''.join(cards)}</div>
  <div class="foot"><span class="brand"><b>欢喜龙虾<em>.</em></b> huanxi.ai</span><span>本地隐私 · 云端聚合 · 每日 07:00</span></div>
</div></body></html>"""


async def shoot(html_path, png_path, vw=820):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": vw, "height": 1200}, device_scale_factor=2)
        await pg.goto("file://" + html_path)
        await pg.wait_for_timeout(600)        # 等 webfont（Inter Tight/Noto）加载，否则 hairline 字回退
        await pg.screenshot(path=png_path, full_page=True)
        await b.close()


def main():
    items = get_items()
    if not items:
        sys.exit(f"✗ {MODULE} 今日无可用条目")
    caption = ""
    if STORIES_FILE:                       # agent(本地 Opus 4.8) 直接供稿模式
        data = json.load(open(STORIES_FILE, encoding="utf-8"))
        if isinstance(data, dict):         # {"stories":[...], "caption":"朋友圈配文"}
            stories = data.get("stories", [])
            caption = (data.get("caption") or "").strip()
        else:                              # 兼容旧版纯数组
            stories = data
    else:
        out = llm(build_prompt(items), SYS)
        if not out:
            sys.exit("✗ LLM 调用失败（本地 Opus 未起？加 --fallback 用 DeepSeek，或用 --stories 亲写）")
        stories = parse_json(out)
    OUT.mkdir(parents=True, exist_ok=True)
    if STYLE == "classic":
        html, vw = render_html(stories, items), 820
    else:
        html, vw = render_html_apple(stories, items), 1242   # 苹果大片·默认
    hp = str(OUT / f"新闻简报-{MODULE}.html")
    pp = str(OUT / f"新闻简报-{MODULE}.png")
    Path(hp).write_text(html, encoding="utf-8")
    asyncio.run(shoot(hp, pp, vw))
    print(f"✅ 新闻简报·{TITLE_CN}（{STYLE}）→ {pp}")
    for i, s in enumerate(stories, 1):
        print(f"  {i}. 【{s['source']}】{s['title']}（{len(s['body'])}字）")
    if caption:                            # 朋友圈配文：图文一起发的「文」
        cp = OUT / f"新闻简报-{MODULE}-朋友圈配文.txt"
        cp.write_text(caption, encoding="utf-8")
        print(f"\n📲 朋友圈配文 → {cp}\n" + "─" * 40 + f"\n{caption}\n" + "─" * 40)


if __name__ == "__main__":
    main()
