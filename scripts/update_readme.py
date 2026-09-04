#!/usr/bin/env python3
"""Update the profile README with the owner's latest public repositories."""

import json
import os
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER = os.getenv("GITHUB_REPOSITORY_OWNER", "mightyalok00")
README = Path("README.md")
START = "<!-- LATEST-REPOS:START -->"
END = "<!-- LATEST-REPOS:END -->"
LIMIT = 6


def fetch_repositories():
    url = (
        f"https://api.github.com/users/{quote(OWNER)}/repos"
        "?per_page=100&sort=updated&direction=desc&type=owner"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{OWNER}-profile-readme-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def clean(text):
    return " ".join((text or "").replace("|", "\|").split())


def render(repositories):
    selected = [
        repo
        for repo in repositories
        if not repo.get("fork")
        and not repo.get("archived")
        and repo.get("name", "").lower() != OWNER.lower()
    ][:LIMIT]

    if not selected:
        return "_No public repositories found._"

    lines = []
    for repo in selected:
        description = clean(repo.get("description")) or "Explore this repository on GitHub."
        details = []
        if repo.get("language"):
            details.append(repo["language"])
        if repo.get("stargazers_count"):
            details.append(f"⭐ {repo['stargazers_count']}")
        suffix = f" ({' · '.join(details)})" if details else ""
        lines.append(f"- [**{repo['name']}**]({repo['html_url']}) — {description}{suffix}")
    return "\n".join(lines)


def main():
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise RuntimeError("README.md is missing the latest-repositories markers")

    replacement = f"{START}\n{render(fetch_repositories())}\n{END}"
    updated = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        lambda _: replacement,
        readme,
        count=1,
        flags=re.DOTALL,
    )
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
