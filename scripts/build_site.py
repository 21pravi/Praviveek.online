#!/usr/bin/env python3
"""
Site builder — run after adding/editing a post, and after each bot run.

1. Scans posts/*.md, reads the front-matter block, rebuilds data/posts.json.
2. Generates feed.xml (RSS) from posts + digests + papers.

Run:  python scripts/build_site.py
"""
import json, re, html
from datetime import datetime, timezone
from pathlib import Path
from email.utils import format_datetime

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATA = ROOT / "data"
SITE = "https://praviveek.online"
TITLE = "Signal — Praviveek Ray"
DESC = "Daily AI and tech digest, research papers, and writing by a working data scientist."


def parse_front_matter(text):
    """Reads the --- key: value --- block at the top of a markdown file."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta, body = {}, m.group(2)
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k == "tags":
            v = [t.strip() for t in v.strip("[]").split(",") if t.strip()]
        meta[k] = v
    return meta, body


def build_posts():
    rows = []
    for f in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        if not meta.get("title"):
            print(f"  ! {f.name}: missing title, skipped")
            continue
        excerpt = meta.get("excerpt") or re.sub(r"[#*`>\[\]]", "", body).strip()[:180] + "…"
        rows.append({
            "slug": f.stem,
            "type": meta.get("type", "writing"),
            "title": meta["title"],
            "date": meta.get("date", datetime.now().strftime("%Y-%m-%d")),
            "tags": meta.get("tags", []),
            "excerpt": excerpt.replace("\n", " "),
            "pdf": meta.get("pdf") or None,
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "posts.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"posts.json — {len(rows)} posts")
    return rows


def load(name, default):
    p = DATA / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def rss(posts):
    news = load("news.json", {"issues": []})
    papers = load("papers.json", {"items": []})
    entries = []

    for p in posts:
        entries.append((p["date"], p["title"], f"{SITE}/post.html?p={p['slug']}", p["excerpt"]))
    for i in news.get("issues", [])[:30]:
        body = i.get("intro", "") + " " + " · ".join(x["title"] for x in i.get("items", [])[:5])
        entries.append((i["date"], i["title"], f"{SITE}/#{i['slug']}", body.strip()))
    for p in papers.get("items", [])[:20]:
        entries.append((p["date"], f"Paper: {p['title']}", p["url"], p.get("summary", "")))

    entries.sort(key=lambda e: e[0], reverse=True)
    entries = entries[:50]

    def item(e):
        date, title, link, desc = e
        try:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            pub = format_datetime(dt)
        except Exception:
            pub = format_datetime(datetime.now(timezone.utc))
        return f"""    <item>
      <title>{html.escape(title)}</title>
      <link>{html.escape(link)}</link>
      <guid isPermaLink="false">{html.escape(link)}</guid>
      <pubDate>{pub}</pubDate>
      <description>{html.escape(desc or '')}</description>
    </item>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(TITLE)}</title>
    <link>{SITE}/</link>
    <description>{html.escape(DESC)}</description>
    <language>en</language>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(item(e) for e in entries)}
  </channel>
</rss>
"""
    (ROOT / "feed.xml").write_text(xml, encoding="utf-8")
    print(f"feed.xml — {len(entries)} entries")


if __name__ == "__main__":
    rss(build_posts())
