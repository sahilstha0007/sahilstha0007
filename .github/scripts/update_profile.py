#!/usr/bin/env python3

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as urlquote
from urllib.request import Request, urlopen

README = Path("README.md")
EXCLUDED_REPO = "sahilstha0007/sahilstha0007"
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
    endpoint = (
        f"https://api.github.com{path}"
        if repo is None
        else f"https://api.github.com/repos/{repo}{path}"
    )
    request = Request(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-bot"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def escape_message(message):
    text = html.escape(" ".join(str(message).split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()|~])", r"\\\1", text)


def github_url(repo, sha=None):
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    base = "https://github.com/" + "/".join(urlquote(part, safe="") for part in parts)
    if sha is None:
        return base
    return f"{base}/commit/{urlquote(sha, safe='')}"


def lookup_commit_message(repo, sha, token):
    try:
        response = api(f"/commits/{sha}", repo, token)
        commit = response.get("commit") if isinstance(response, dict) else None
        message = commit.get("message") if isinstance(commit, dict) else None
    except (OSError, TypeError, ValueError, KeyError):
        return None
    return message if isinstance(message, str) else None


def format_activity(events, message_lookup=None):
    if not isinstance(events, list):
        raise TypeError("events response was not a list")

    lines = []
    seen = set()
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "PushEvent":
            continue
        if not event.get("public", True):
            continue

        repository = event.get("repo") or {}
        if not isinstance(repository, dict):
            continue
        repo = repository.get("name")
        if not isinstance(repo, str) or repo.casefold() == EXCLUDED_REPO:
            continue

        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        commits = payload.get("commits")
        if not isinstance(commits, list):
            commits = []

        commit = payload.get("head_commit")
        if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str) or not commit["sha"]:
            commit = next(
                (
                    item
                    for item in commits
                    if isinstance(item, dict)
                    and isinstance(item.get("sha"), str)
                    and item["sha"]
                ),
                None,
            )

        if isinstance(commit, dict) and isinstance(commit.get("sha"), str) and commit["sha"]:
            sha = commit["sha"]
            message = commit.get("message")
            if not isinstance(message, str):
                message = next(
                    (
                        item.get("message")
                        for item in commits
                        if isinstance(item, dict) and isinstance(item.get("message"), str)
                    ),
                    "",
                )
        else:
            sha = payload.get("head")
            message = ""
            if not isinstance(sha, str) or not sha:
                continue

        repo_url = github_url(repo)
        commit_url = github_url(repo, sha)
        if not repo_url or not commit_url:
            continue

        key = (repo.casefold(), sha)
        if key in seen:
            continue
        if not isinstance(message, str) or not message.strip():
            ref = payload.get("ref")
            branch = ref[11:] if isinstance(ref, str) and ref.startswith("refs/heads/") else ""
            fallback = f"pushed to {branch}" if branch else "pushed a commit"
            if message_lookup is not None:
                try:
                    message = message_lookup(repo, sha)
                except (OSError, TypeError, ValueError, KeyError):
                    message = ""
            if not isinstance(message, str) or not message.strip():
                message = fallback
        message = message.strip().splitlines()[0].strip()
        lines.append(
            f"- **[{escape_message(repo)}]({repo_url})** — "
            f"[{escape_message(message[:120])}]({commit_url})"
        )
        seen.add(key)
        if len(lines) == 5:
            break

    return "\n".join(lines) or "_No recent public pushes yet._"


def recent_activity(repo, token):
    owner = repo.split("/", 1)[0]
    try:
        events = api(f"/users/{owner}/events/public?per_page=100", None, token)
        return format_activity(
            events,
            lambda repo, sha: lookup_commit_message(repo, sha, token),
        )
    except (OSError, TypeError, ValueError, KeyError) as error:
        print(f"activity unavailable: {error}", file=sys.stderr)
        return None


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

    activity = format_activity(
        [
            {
                "type": "PushEvent",
                "public": True,
                "repo": {"name": EXCLUDED_REPO},
                "payload": {"head_commit": {"sha": "skip", "message": "skip"}},
            },
            {
                "type": "PushEvent",
                "public": True,
                "repo": {"name": "sahilstha0007/demo"},
                "payload": {
                    "head_commit": {
                        "sha": "abc123",
                        "message": "ship | [it] <now>",
                    }
                },
            },
            {
                "type": "PushEvent",
                "public": True,
                "repo": {"name": "sahilstha0007/live-demo"},
                "payload": {
                    "before": "0000000",
                    "head": "deadbeef",
                    "push_id": 123,
                    "ref": "refs/heads/main",
                    "repository_id": 456,
                },
            },
        ]
    )
    assert "ship \\| \\[it\\] &lt;now&gt;" in activity
    assert "deadbeef" in activity
    assert "pushed to main" in activity
    assert EXCLUDED_REPO not in activity

    lookup_calls = []

    def lookup(repo, sha):
        lookup_calls.append((repo, sha))
        return "looked up | message\nsecond line"

    lookup_events = [
        {
            "type": "PushEvent",
            "repo": {"name": "sahilstha0007/lookup"},
            "payload": {"head": str(index), "ref": "refs/heads/main"},
        }
        for index in range(6)
    ]
    looked_up = format_activity(lookup_events, lookup)
    assert "looked up \\| message" in looked_up
    assert "second line" not in looked_up
    assert len(lookup_calls) == 5
    assert format_activity([]) == "_No recent public pushes yet._"
    recent = format_activity(
        [
            {
                "type": "PushEvent",
                "repo": {"name": f"owner/repo-{index}"},
                "payload": {"head_commit": {"sha": str(index), "message": "change"}},
            }
            for index in range(6)
        ]
    )
    assert len(recent.splitlines()) == 5
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
    activity_text = recent_activity(repo, token)
    if activity_text is not None:
        changed = splice("RECENT_ACTIVITY", activity_text) or changed
    print("README updated" if changed else "README already up to date")


if __name__ == "__main__":
    main()
