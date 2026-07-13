#!/usr/bin/env python3
"""
新闻简报抓取器 (news-brief fetcher)
读 ../config/rss-feeds.json 的 news_feeds，新鲜抓取 → 按模块/地区分组 → 输出。
新闻读完即弃，不写入任何知识库。

用法：
  python3 news-brief.py            # 全部模块
  python3 news-brief.py 金融       # 单模块：金融 / 三地 / 大学艺术
  python3 news-brief.py --hours 48 # 只取最近 N 小时（默认 36）
  python3 news-brief.py --json     # 输出 JSON（给渲染层/LLM 提炼用）
"""

import sys, os, json, time, re, warnings
import concurrent.futures as cf
from pathlib import Path
from datetime import datetime, timezone, timedelta

import feedparser, requests, subprocess
warnings.filterwarnings("ignore")
requests.packages.urllib3.disable_warnings()

# ── 自带配置优先；找不到再退回 ~/JoyClaw（便于本地开发）──
SKILL = Path(__file__).resolve().parent.parent
CONFIG = SKILL / "config" / "rss-feeds.json"
if not CONFIG.exists():
    CONFIG = Path.home() / "JoyClaw" / "config" / "rss-feeds.json"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,text/xml,*/*"}

# ── 参数 ──────────────────────────────────────────────
ARGS = sys.argv[1:]
AS_JSON = "--json" in ARGS
HOURS = 36
if "--hours" in ARGS:
    HOURS = int(ARGS[ARGS.index("--hours") + 1])
PICK_MODULE = next((a for a in ARGS if not a.startswith("--") and a not in
                    (str(HOURS),)), None)
# 每个地区/类别在简报里保留几条
CAP = {"金融": 12, "香港": 6, "中国": 6, "世界": 6, "大学": 6, "艺术": 5}


# ── RSSHub 域名与密钥：绝不焊死在 config，只从环境变量/本地 gitignored 文件解析 ──
#    分发时由 joy_env / joy_profile 注入 RSSHUB_BASE / RSSHUB_KEY；
#    本地回退读 ~/JoyClaw/.rsshub-base / .rsshub-access-key；
#    都没有 → 空串，那几个 RSSHub 源优雅跳过（公共源照常）。
def _resolve_local(env_name, filename):
    v = os.environ.get(env_name, "").strip()
    if v:
        return v
    f = Path.home() / "JoyClaw" / filename
    try:
        return f.read_text(encoding="utf-8").strip() if f.exists() else ""
    except Exception:
        return ""
RSSHUB_KEY = _resolve_local("RSSHUB_KEY", ".rsshub-access-key")
RSSHUB_BASE = _resolve_local("RSSHUB_BASE", ".rsshub-base").rstrip("/")


def fetch(feed):
    """抓单个源 → [(title, source, link, summary, ts)]"""
    name, url = feed["name"], feed["url"]
    if "${RSSHUB_BASE}" in url and not RSSHUB_BASE:
        return name, "SKIP(no RSSHUB_BASE)", out       # 未配置自托管 RSSHub → 跳过
    url = url.replace("${RSSHUB_BASE}", RSSHUB_BASE)   # 占位符 → 运行时域名
    url = url.replace("${RSSHUB_KEY}", RSSHUB_KEY)     # 占位符 → 运行时密钥
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=12, verify=False)
        if r.status_code >= 400:
            return name, f"HTTP{r.status_code}", out
        d = feedparser.parse(r.content)
        for e in d.entries:
            ts = None
            for k in ("published_parsed", "updated_parsed"):
                if e.get(k):
                    ts = datetime.fromtimestamp(time.mktime(e[k]), tz=timezone.utc)
                    break
            title = (e.get("title") or "").strip()
            if "news.google.com" in url and " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()   # 去掉 Google News 的「 - 出处」后缀
            summ = e.get("summary") or ""
            if not summ and e.get("content"):
                summ = e["content"][0].get("value", "")
            summ = re.sub(r"<[^>]+>", "", summ).strip()[:500]
            out.append({
                "title": title,
                "source": name,
                "link": e.get("link", ""),
                "summary": summ,
                "ts": ts,
            })
        return name, "OK", out
    except Exception as ex:
        return name, f"ERR:{type(ex).__name__}", out


def collect(feeds):
    """并发抓一组源，过滤到最近 HOURS 小时，去重，按来源轮转保多样性"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    items, status = [], []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for name, st, rows in ex.map(fetch, feeds):
            status.append((name, st, len(rows)))
            items.extend(rows)
    # 有时间戳的按新鲜度过滤；没时间戳的保留（部分源不给日期）
    fresh = [i for i in items if i["ts"] is None or i["ts"] >= cutoff]
    if len([i for i in fresh if i["ts"]]) < 3:        # 太少则放宽窗口
        fresh = items
    fresh.sort(key=lambda i: i["ts"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    # 去重（同标题）
    seen, uniq = set(), []
    for i in fresh:
        k = i["title"].lower()
        if k and k not in seen:
            seen.add(k); uniq.append(i)
    # 按来源轮转，保证多样性（不让某个高频源刷屏，每个点名的源都露面）
    from collections import defaultdict, deque
    bysrc = defaultdict(deque)
    for i in uniq:
        bysrc[i["source"]].append(i)
    queues, rr = list(bysrc.values()), []
    while queues:
        for q in list(queues):
            if q:
                rr.append(q.popleft())
            else:
                queues.remove(q)
    return rr, status


def fmt_ts(ts):
    if not ts:
        return "  --  "
    return ts.astimezone().strftime("%m-%d %H:%M")


def main():
    cfg = json.load(open(CONFIG))
    nf = cfg["news_feeds"]
    modules = [PICK_MODULE] if PICK_MODULE else ["金融", "三地", "大学艺术"]

    # AI人物 模块委托给 ai-figure-fetch.py（独立管线：X feed → master_intel）
    if PICK_MODULE == "AI人物":
        af = os.path.join(os.path.dirname(__file__), "ai-figure-fetch.py")
        result = subprocess.run(["python3", af, "--hours", str(HOURS)],
                                capture_output=True, text=True, timeout=180)
        print(result.stdout)
        return

    result = {}
    for mod in modules:
        if mod not in nf:
            print(f"⚠️ 未知模块: {mod}（可选 金融/三地/大学艺术/AI人物）"); continue
        block = nf[mod]
        # 金融是 list；三地/大学艺术是 {子组: list}
        groups = {"_": block} if isinstance(block, list) else block
        result[mod] = {}
        for sub, feeds in groups.items():
            if sub != "_" and sub.startswith("_"):
                continue
            items, status = collect(feeds)
            cap = CAP.get(sub if sub != "_" else mod, 6)
            result[mod][sub] = {"items": items[:cap], "status": status}

    if AS_JSON:
        # 给渲染层/LLM：精简结构
        slim = {m: {s: [{"title": i["title"], "source": i["source"],
                         "link": i["link"], "time": fmt_ts(i["ts"]),
                         "summary": i.get("summary", "")}
                        for i in g["items"]]
                    for s, g in subs.items()}
                for m, subs in result.items()}
        print(json.dumps(slim, ensure_ascii=False, indent=2))
        return

    # 人读版
    print(f"\n📰 欢喜每日新闻简报  ·  {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  近 {HOURS}h\n")
    for mod, subs in result.items():
        print(f"{'='*60}\n【{mod}模块】\n{'='*60}")
        for sub, g in subs.items():
            label = "" if sub == "_" else f" — {sub}"
            ok = sum(1 for _, st, _ in g["status"] if st == "OK")
            print(f"\n▌{mod}{label}  ({ok}/{len(g['status'])} 源OK)")
            if not g["items"]:
                print("   (近期无更新)")
            for i in g["items"]:
                print(f"   · [{fmt_ts(i['ts'])}] {i['title'][:70]}")
                print(f"       {i['source']}  {i['link'][:72]}")
        print()


if __name__ == "__main__":
    main()
