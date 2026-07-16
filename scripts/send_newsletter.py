#!/usr/bin/env python3
"""
Email the latest digest (or roundup) to Buttondown subscribers.

Reads data/news.json, takes the newest issue, renders it as markdown, and
POSTs it to Buttondown. Records what it sent in data/sent.json so re-running
the workflow can't spam your list twice.

Run:   python scripts/send_newsletter.py            # send newest issue
       python scripts/send_newsletter.py --dry-run  # print, don't send
Env:   BUTTONDOWN_API_KEY   (GitHub Actions secret — never hardcode)

No key set? Exits quietly with code 0 so the workflow still passes.
"""
import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "data" / "news.json"
SENT = ROOT / "data" / "sent.json"
SITE = "https://praviveek.online"

API = "https://api.buttondown.com/v1/emails"
API_VERSION = "2026-04-01"   # pinned: on this version POST defaults to draft
DRY = "--dry-run" in sys.argv


def load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def render(issue):
    """Turn an issue into markdown. Summaries are ours; links go to the source."""
    kind = issue.get("type", "digest")
    lines = []

    if issue.get("intro"):
        lines += [f"*{issue['intro']}*", ""]

    for n, item in enumerate(issue.get("items", []), 1):
        title = item.get("title", "").strip()
        url = (item.get("url") or "").strip()
        summary = (item.get("summary") or "").strip()
        source = (item.get("source") or "").strip()

        if kind == "roundup":
            # Roundup themes have no URL — they're synthesis, not links.
            lines += [f"## {n}. {title}", "", summary, ""]
        else:
            head = f"**{n}. [{title}]({url})**" if url else f"**{n}. {title}**"
            lines += [head, ""]
            if summary:
                lines += [summary, ""]
            if source:
                lines += [f"<sub>Source: {source}</sub>", ""]

    lines += [
        "---",
        "",
        f"Read this on the web: [{SITE}]({SITE})",
        "",
        "*Summaries are written by an AI assistant and link to the original "
        "reporting. Built and maintained by Praviveek Ray — "
        f"[portfolio](https://praviveek.com).*",
    ]
    return "\n".join(lines)


def post(subject, body, key):
    payload = json.dumps({
        "subject": subject,
        "body": body,
        "status": "about_to_send",
    }).encode()

    req = urllib.request.Request(API, data=payload, method="POST")
    req.add_header("Authorization", f"Token {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Version", API_VERSION)
    # Required by Buttondown the first time an API key sends via about_to_send.
    # Harmless on subsequent calls.
    req.add_header("X-Buttondown-Live-Dangerously", "true")

    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not key and not DRY:
        print("No BUTTONDOWN_API_KEY — skipping newsletter (this is fine).")
        return

    doc = load(NEWS, {"issues": []})
    issues = doc.get("issues", [])
    if not issues:
        print("No issues to send.")
        return

    issue = issues[0]                      # newest, list is kept sorted
    slug = issue.get("slug", "")

    sent = load(SENT, {"slugs": []})
    if slug in sent.get("slugs", []):
        print(f"Already emailed {slug} — skipping (no double-send).")
        return

    subject = issue.get("title", "AI & Tech Digest")
    body = render(issue)

    if DRY:
        print(f"--- SUBJECT ---\n{subject}\n\n--- BODY ---\n{body}")
        return

    try:
        res = post(subject, body, key)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        print(f"! Buttondown returned {e.code}: {detail}", file=sys.stderr)
        # Don't fail the workflow — the site already published fine.
        return
    except Exception as e:
        print(f"! Send failed: {e}", file=sys.stderr)
        return

    print(f"Emailed '{subject}' — status={res.get('status')} id={res.get('id')}")

    sent.setdefault("slugs", []).insert(0, slug)
    sent["slugs"] = sent["slugs"][:120]
    SENT.write_text(json.dumps(sent, indent=2))


if __name__ == "__main__":
    main()
