#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日财经快报 · 确定性生成器
设计目标：把「抓取 → 精选 → 撰写 → 落档」全部做成不依赖订阅桥（localhost:3456）的确定性流程。
大脑用 DeepSeek API（按量付费、永远在线）；DeepSeek 万一不通，自动降级为模板直出——内容生成永不空手。

用法：
    python3 finance_brief_gen.py            # 正常：抓取 + DeepSeek 撰写 + 落档 + 打印
    python3 finance_brief_gen.py --no-llm   # 仅模板兜底（本地测试 / 离线）
    python3 finance_brief_gen.py --check     # 只检查今天是否已生成，已生成则打印路径并退出 0

退出码：0 成功；2 抓取失败；3 落档失败。
最终产物：~/JoyClaw/01-信息箱/简报/YYYY-MM-DD/finance_brief.md（推送正文）
         同目录 source.json（抓取原始数据）
"""
import sys, os, json, subprocess, datetime, urllib.request, urllib.error, re, ssl

def _ssl_ctx():
    """macOS 下 urllib 默认找不到根证书，用 certifi；没有则退回不校验，保证 DeepSeek 永远打得通。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl._create_unverified_context()

HOME = os.path.expanduser("~")
FETCH = os.path.join(HOME, ".clacky/skills/news-brief/scripts/news-brief.py")
CONFIG = os.path.join(HOME, ".clacky/config.yml")
TODAY = datetime.date.today().strftime("%Y-%m-%d")
WEEKDAY = "一二三四五六日"[datetime.date.today().weekday()]
OUTDIR = os.path.join(HOME, "JoyClaw/01-信息箱/简报", TODAY)
OUTMD = os.path.join(OUTDIR, "finance_brief.md")
OUTJSON = os.path.join(OUTDIR, "source.json")


def log(m):
    print(f"[finance_brief_gen] {m}", file=sys.stderr, flush=True)


def get_deepseek_key():
    """从 config.yml 里读 deepseek 的 api_key，不引第三方 yaml 依赖。"""
    try:
        txt = open(CONFIG, encoding="utf-8").read()
    except Exception:
        return None
    in_ds = False
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("- model:"):
            in_ds = "deepseek" in s
        elif in_ds and s.startswith("api_key:"):
            return s.split("api_key:", 1)[1].strip()
    return None


def fetch_news(hours=24):
    """跑抓取脚本，返回扁平的新闻 list[{title,source,summary,link,time}]。"""
    for h in (hours, 48):
        try:
            out = subprocess.run(
                [sys.executable, FETCH, "金融", "--json", "--hours", str(h)],
                capture_output=True, text=True, timeout=120,
            )
            data = json.loads(out.stdout)
            items = []
            for _domain, groups in data.items():
                for _g, arr in groups.items():
                    for it in arr:
                        items.append(it)
            # 去重（按标题）
            seen, uniq = set(), []
            for it in items:
                t = (it.get("title") or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    uniq.append(it)
            if uniq:
                log(f"抓取成功 hours={h} 共 {len(uniq)} 条")
                return uniq
        except Exception as e:
            log(f"抓取失败 hours={h}: {e}")
    return []


def deepseek_write(items, key):
    """让 DeepSeek 精选 6 条 + 写成中文快报 + 朋友圈文案。失败返回 None。"""
    if not key:
        return None
    pool = [
        {"title": it.get("title", ""), "source": it.get("source", ""),
         "summary": (it.get("summary", "") or "")[:300], "link": it.get("link", "")}
        for it in items[:40]
    ]
    prompt = f"""你是一流，欢喜的AI助理。今天是 {TODAY} 周{WEEKDAY}。
下面是过去24小时抓取的财经新闻池（JSON），请从中精选 6 条最重要的（覆盖宏观政策/市场动向A股港股美股/产业热点/人物观点），写成中文财经快报。

每条严格用这个格式：
**序号. 信源 · 标题**
摘要（约140字，含关键数据与影响分析，基于给定 summary，不得编造数字）
🔗 原文链接（有 link 就放，没有就省略这行）

6 条之后，另起一段写约 300 字朋友圈文案：第一人称、有观点、有温度，结合欢喜「人生资产/杠铃策略/不亏钱」的视角。

只输出快报正文，不要任何前后缀说明。

新闻池：
{json.dumps(pool, ensure_ascii=False)}
"""
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7, "max_tokens": 3000,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90, context=_ssl_ctx()) as r:
            resp = json.loads(r.read())
        text = resp["choices"][0]["message"]["content"].strip()
        if len(text) > 200:
            log("DeepSeek 撰写成功")
            return text
        log("DeepSeek 返回过短，降级模板")
    except Exception as e:
        log(f"DeepSeek 失败，降级模板: {e}")
    return None


def template_write(items):
    """零依赖兜底：直接把前 6 条排版成快报。永不失败。"""
    picks = items[:6]
    lines = []
    for i, it in enumerate(picks, 1):
        title = (it.get("title") or "").strip()
        src = (it.get("source") or "").strip()
        summ = (it.get("summary") or "").strip()
        summ = re.sub(r"^【.*?】", "", summ)[:160]
        link = (it.get("link") or "").strip()
        lines.append(f"**{i:02d}. {src} · {title}**")
        lines.append(summ)
        if link:
            lines.append(f"🔗 {link}")
        lines.append("")
    body = "\n".join(lines)
    pl = ("今早的财经动态都在上面了。市场每天都在变，噪音永远比信号多，"
          "我们能做的就是守住自己的底盘：现金留够、配置分散、看得懂的才下手。"
          "不被消息牵着走，是这个时代最贵的能力。地缘和政策我们左右不了，"
          "但自己的人生资产表，今天就能多看一眼。——一流")
    return body + "\n\n**朋友圈文案**\n\n> " + pl


def main():
    args = sys.argv[1:]
    if "--check" in args:
        if os.path.exists(OUTMD):
            print(OUTMD)
            sys.exit(0)
        else:
            print("NOT_GENERATED")
            sys.exit(1)

    no_llm = "--no-llm" in args
    items = fetch_news()
    if not items:
        log("抓取彻底失败")
        print("⚠️ daily_finance_brief 抓取失败｜请手动检查抓取脚本")
        sys.exit(2)

    key = None if no_llm else get_deepseek_key()
    body = deepseek_write(items, key) if not no_llm else None
    used = "deepseek"
    if not body:
        body = template_write(items)
        used = "template"

    header = f"## 📊 财经快报 · {TODAY}（周{WEEKDAY}）\n\n"
    footer = f"\n\n---\n_数据来源：财联社/格隆汇等（过去24h）· 生成：{used} · 共 {len(items)} 条候选_"
    full = header + body + footer

    try:
        os.makedirs(OUTDIR, exist_ok=True)
        with open(OUTMD, "w", encoding="utf-8") as f:
            f.write(full)
        with open(OUTJSON, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"落档失败: {e}")
        print(full)  # 至少把内容吐出去
        sys.exit(3)

    log(f"完成 used={used} 落档={OUTMD}")
    print(full)


if __name__ == "__main__":
    main()
