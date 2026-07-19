#!/usr/bin/env python3
"""
AI人物素材抓取器 — 先刷新 X feed，再从 master_intel 读最近 N 小时数据，
输出与 news-brief.py 一致的 JSON 结构，供 agent 选材和写作。
用法:
  python3 ai-figure-fetch.py               # 默认 48h
  python3 ai-figure-fetch.py --hours 72    # 72h 窗口
  python3 ai-figure-fetch.py --no-refresh  # 跳过 x-feed 刷新（素材已有）
"""
import sys, os, json, sqlite3, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
def _db():
    try:
        sys.path.insert(0, os.path.expanduser("~/.clacky/lib"))
        import joy_env
        return Path(joy_env.db_path())
    except Exception:
        pass
    jc = Path.home() / "JoyClaw" / "joy.db"
    return jc if jc.exists() else SKILL / "data" / "joy.db"
DB = _db()

ARGS = sys.argv[1:]
HOURS = 48
if "--hours" in ARGS:
    HOURS = int(ARGS[ARGS.index("--hours") + 1])
NO_REFRESH = "--no-refresh" in ARGS

# ── Step 1: 刷新 X feed ──
if not NO_REFRESH:
    x_feed = SCRIPTS / "x-feed.py"
    result = subprocess.run(["python3", str(x_feed)], capture_output=True, text=True, timeout=180)
    print(result.stdout.strip(), file=sys.stderr)

# ── Step 2: 从 master_intel 读最近 N 小时数据 ──
con = sqlite3.connect(str(DB))
cutoff = (datetime.now(timezone.utc) - timedelta(hours=HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
rows = con.execute(
    "SELECT m.name, m.title, COALESCE(NULLIF(i.summary,''), i.content, ''), "
    "i.url, i.published_at "
    "FROM master_intel i JOIN masters m ON m.id=i.master_id "
    "WHERE i.created_at >= datetime('now', ? || ' hours') "
    "ORDER BY i.published_at DESC LIMIT 50",
    (f"-{HOURS}",)
).fetchall()
con.close()

items = []
for name, title, content, url, ts in rows:
    content = (content or "").strip()
    if not content:
        continue
    items.append({
        "source": name,
        "title": (title or content[:40]).strip(),
        "summary": content[:600],
        "link": url or "",
        "time": ts or "",
    })

out = {
    "module": "AI人物",
    "hours": HOURS,
    "count": len(items),
    "items": items,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
