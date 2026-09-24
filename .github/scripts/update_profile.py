#!/usr/bin/env python3

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

README = Path("README.md")
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


def api(path, repo, token):
    request = Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-bot"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def escape_message(message):
    text = html.escape(" ".join(message.split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()|~])", r"\\\1", text)


def guestbook(repo, token):
    try:
        issue = api("/issues/1", repo, token)
        total = int(issue.get("comments", 0))
        page = max(1, (total + 99) // 100)
        comments = api(f"/issues/1/comments?per_page=100&page={page}", repo, token)
    except (OSError, TypeError, ValueError) as error:
        print(f"guestbook unavailable: {error}", file=sys.stderr)
        return None

    if not comments:
        return f"_No signatures yet — [be the first!](https://github.com/{repo}/issues/1)_"

    lines = []
    for comment in comments[-10:]:
        user = comment.get("user") or {}
        login = html.escape(user.get("login", "unknown"), quote=False)
        profile_url = user.get("html_url", "https://github.com")
        body = (comment.get("body") or "").strip()
        message = escape_message((body.splitlines()[0] if body else "(no message)")[:80])
        lines.append(f"| [@{login}]({profile_url}) | {message} |")

    return "| Visitor | Message |\n|---|---|\n" + "\n".join(lines) + f"\n\n**{total}** signatures so far"


def quote():
    index = datetime.now(timezone.utc).date().toordinal() % len(QUOTES)
    text, author = QUOTES[index]
    return f"> [!NOTE]\n> {text}\n> — *{author}*"


def replace_marked(source, marker, content):
    pattern = re.compile(
        rf"(<!-- {re.escape(marker)}:START -->\n)(.*?)(\n<!-- {re.escape(marker)}:END -->)",
        re.DOTALL,
    )
    updated, count = pattern.subn(
        lambda match: f"{match.group(1)}{content}{match.group(3)}", source
    )
    if count != 1:
        raise ValueError(f"expected one {marker} marker, found {count}")
    return updated


def splice(marker, content):
    source = README.read_text(encoding="utf-8")
    updated = replace_marked(source, marker, content)
    if updated == source:
        return False
    README.write_text(updated, encoding="utf-8")
    return True


def self_test():
    source = "before\n<!-- TEST:START -->\nold\n<!-- TEST:END -->\nafter"
    expected = "before\n<!-- TEST:START -->\nnew\\1\n<!-- TEST:END -->\nafter"
    assert replace_marked(source, "TEST", "new\\1") == expected
    escaped = escape_message("hello | <tag> [x]")
    assert "&lt;tag&gt;" in escaped
    assert "\\|" in escaped
    assert "\\[" in escaped
    assert "\\~" in escape_message("~text~")
    print("self-test passed")


def main():
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        return
    if sys.argv[1:]:
        raise SystemExit("usage: update_profile.py [--self-test]")

    repo = os.environ["REPO"]
    token = os.environ["GH_TOKEN"]
    changed = splice("QUOTE", quote())
    guestbook_text = guestbook(repo, token)
    if guestbook_text is not None:
        changed = splice("GUESTBOOK", guestbook_text) or changed
    print("README updated" if changed else "README already up to date")


if __name__ == "__main__":
    main()
