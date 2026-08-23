#!/usr/bin/env python3
"""Injects live guestbook entries + a daily quote into README.md."""

import json
import os
import random
import re
import urllib.request

REPO = os.environ["REPO"]
TOKEN = os.environ["GH_TOKEN"]
README = "README.md"

QUOTES = [
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Any sufficiently advanced bug is indistinguishable from a feature.", "Eric S. Raymond"),
    ("It works on my machine.", "Every developer, eventually"),
    ("There are two hard things in CS: cache invalidation, naming things, and off-by-one errors.", "Anonymous"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Simplicity is prerequisite for reliability.", "Edsger W. Dijkstra"),
    ("Weeks of coding can save you hours of planning.", "Unknown"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("Deleted code is debugged code.", "Jeff Sickel"),
    ("Rebooting is the sincerest form of flattery.", "Every Arch user"),
]


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "profile-bot"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def guestbook():
    try:
        comments = api(f"/repos/{REPO}/issues/1/comments")
    except Exception:
        return "_No signatures yet — [be the first!](https://github.com/sahilstha0007/sahilstha0007/issues/1)_"
    if not comments:
        return "_No signatures yet — [be the first!](https://github.com/sahilstha0007/sahilstha0007/issues/1)_"
    emojis = ["🔥", "⚡", "🚀", "🌟", "💜", "🦄", "🍕", "☕"]
    lines = []
    for c in comments[-10:]:
        msg = c["body"].split("\n")[0][:80]
        lines.append(f'| **[@{c["user"]["login"]}]({c["user"]["html_url"]})** | {msg} |')
    header = "| Visitor | Message |\n|---|---|\n"
    total = f"\n\n🗣️ **{len(comments)}** signatures so far"
    return header + "\n".join(lines) + total


def quote():
    q, a = random.choice(QUOTES)
    return f'> [!NOTE]\n> {q}\n> — *{a}*'


def splice(markers, content):
    pattern = re.compile(
        rf"(<!-- {markers}:START -->\n)(.*?)(\n<!-- {markers}:END -->)", re.DOTALL
    )
    src = open(README).read()
    open(README, "w").write(pattern.sub(rf"\g<1>{content}\g<3>", src))


splice("GUESTBOOK", guestbook())
splice("QUOTE", quote())
print("README updated")
