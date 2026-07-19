#!/usr/bin/env python3
"""
x-feed · 直接拉 zarazhangrui/follow-builders 的中心化 X feed → 写 master_intel
无需 X cookie / 无需用户 X 账号 / 一次 HTTP（中心服务每天刷新提交到仓库）。
锚定 follow-builders 精选的 ~26 个一流 AI builder。

用法：
  python3 x-feed.py            # 拉 feed 写库
  python3 x-feed.py --dry      # 只看不写
"""
import sys, json, ssl, sqlite3, urllib.request
from pathlib import Path

FEED_URL = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json"
def _db():
    """欢喜龙虾单一权威解析：joy_env.db_path() → ~/JoyClaw/joy.db → skill 自带 data/"""
    try:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.expanduser("~/.clacky/lib"))
        import joy_env
        return Path(joy_env.db_path())
    except Exception:
        pass
    jc = Path.home() / "JoyClaw" / "joy.db"
    return jc if jc.exists() else Path(__file__).resolve().parent.parent / "data" / "joy.db"
DB = _db()

def _ensure_schema(con):
    con.execute("CREATE TABLE IF NOT EXISTS masters("
                "id INTEGER PRIMARY KEY, name TEXT, title TEXT, x_handle TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS master_intel("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, master_id INTEGER, handle TEXT,"
                "channel TEXT, title TEXT, url TEXT, content TEXT, summary TEXT,"
                "published_at TEXT, created_at TEXT DEFAULT (datetime('now')))")
DRY = "--dry" in sys.argv


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "huanxiai-xfeed/1.0"})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception:
        # 证书拦截环境降级
        try:
            ctx = ssl.create_default_context(); ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return json.loads(r.read().decode())
        except Exception as e2:
            sys.exit(f"✗ 拉取 feed 失败: {e2}")


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    feed = fetch_feed()
    people = feed.get("x", [])
    print(f"feed 生成于 {feed.get('generatedAt')} · {len(people)} 人 · "
          f"{sum(len(p.get('tweets', [])) for p in people)} 条推文")

    con = sqlite3.connect(DB)
    _ensure_schema(con)
    # 建 handle→master_id 映射（小写匹配）
    id_by_handle = {}
    for mid, h in con.execute("SELECT id, lower(x_handle) FROM masters WHERE x_handle LIKE '@%'"):
        id_by_handle[h] = mid

    new, skip_unknown = 0, []
    for p in people:
        handle = "@" + p["handle"]
        mid = id_by_handle.get(handle.lower())
        if mid is None:
            skip_unknown.append(handle)        # 不在 masters 名单里的，先记下
        for tw in p.get("tweets", []):
            url = tw.get("url", "")
            text = (tw.get("text") or "").strip()
            if not text:
                continue
            if url and con.execute("SELECT 1 FROM master_intel WHERE url=?", (url,)).fetchone():
                continue                        # 去重
            if DRY:
                new += 1; continue
            con.execute(
                """INSERT INTO master_intel
                   (master_id, handle, channel, title, url, content, summary, published_at)
                   VALUES (?,?, 'x', ?, ?, ?, '', ?)""",
                (mid, handle, text[:40], url, text, tw.get("createdAt", "")))
            new += 1
    if not DRY:
        con.commit()
    con.close()
    print(f"{'[DRY] 将' if DRY else '✅'}新入库 {new} 条 → master_intel")
    if skip_unknown:
        print(f"⚠️ 不在 masters 名单(仍入库,master_id 空): {skip_unknown}")


if __name__ == "__main__":
    main()
