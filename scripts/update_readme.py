#!/usr/bin/env python3
"""Update the profile README and its repository-language chart."""

import json
import math
import os
import re
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER = os.getenv("GITHUB_REPOSITORY_OWNER", "mightyalok00")
README = Path("README.md")
LANGUAGE_CHART = Path("assets/code-language-distribution.svg")
START = "<!-- LATEST-REPOS:START -->"
END = "<!-- LATEST-REPOS:END -->"
LIMIT = 6
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "Jupyter Notebook": "#DA5B0B",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "SQL": "#336791",
    "Shell": "#89E051",
    "Java": "#B07219",
    "C++": "#F34B7D",
    "C": "#555555",
    "R": "#198CE7",
}
FALLBACK_COLORS = ["#8B5CF6", "#14B8A6", "#F97316", "#EC4899", "#64748B"]


def github_json(url):
    """Fetch one JSON response from GitHub, using the Actions token when present."""
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


def fetch_repositories():
    url = (
        f"https://api.github.com/users/{quote(OWNER)}/repos"
        "?per_page=100&sort=updated&direction=desc&type=owner"
    )
    return github_json(url)


def active_projects(repositories):
    return [
        repo
        for repo in repositories
        if not repo.get("fork")
        and not repo.get("archived")
        and repo.get("name", "").lower() != OWNER.lower()
    ]


def clean(text):
    return " ".join((text or "").replace("|", "\\|").split())


def render(repositories):
    selected = active_projects(repositories)[:LIMIT]

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


def aggregate_languages(repositories):
    """Add GitHub's detected language bytes across active public projects."""
    totals = {}
    for repo in active_projects(repositories):
        for language, byte_count in github_json(repo["languages_url"]).items():
            totals[language] = totals.get(language, 0) + byte_count
    return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))


def point(cx, cy, radius, angle):
    radians = math.radians(angle - 90)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def pie_path(cx, cy, radius, start_angle, end_angle):
    start_x, start_y = point(cx, cy, radius, start_angle)
    end_x, end_y = point(cx, cy, radius, end_angle)
    large_arc = 1 if end_angle - start_angle > 180 else 0
    return (
        f"M {cx:.3f} {cy:.3f} L {start_x:.3f} {start_y:.3f} "
        f"A {radius} {radius} 0 {large_arc} 1 {end_x:.3f} {end_y:.3f} Z"
    )


def render_language_chart(languages, repository_count):
    if not languages:
        raise RuntimeError("GitHub returned no language data for public repositories")

    total = sum(languages.values())
    items = list(languages.items())
    colors = {
        language: LANGUAGE_COLORS.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])
        for index, (language, _) in enumerate(items)
    }
    angle = 0.0
    slices = []
    legend = []
    for index, (language, byte_count) in enumerate(items):
        share = byte_count / total
        next_angle = 360.0 if index == len(items) - 1 else angle + share * 360
        color = colors[language]
        slices.append(
            f'<path d="{pie_path(205, 230, 145, angle, next_angle)}" fill="{color}">'
            f'<title>{escape(language)}: {share * 100:.1f}% ({byte_count:,} bytes)</title></path>'
        )
        y = 101 + index * 39
        legend.append(
            f'<rect x="410" y="{y}" width="18" height="18" rx="4" fill="{color}"/>'
            f'<text x="442" y="{y + 14}" class="label">{escape(language)}</text>'
            f'<text x="745" y="{y + 14}" class="value" text-anchor="end">{share * 100:.1f}%</text>'
        )
        angle = next_angle

    height = max(470, 145 + len(items) * 39)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(OWNER)} public repository code language distribution</title>
  <desc id="desc">Pie chart generated from {repository_count} active, non-fork public repositories using GitHub language byte totals.</desc>
  <style>
    .bg {{ fill: #ffffff; }}
    .heading {{ fill: #111827; font: 700 24px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .subheading {{ fill: #6b7280; font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .label {{ fill: #374151; font: 600 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .value {{ fill: #111827; font: 700 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #0d1117; }} .heading, .value {{ fill: #f0f6fc; }}
      .subheading {{ fill: #8b949e; }} .label {{ fill: #c9d1d9; }}
    }}
  </style>
  <rect class="bg" width="800" height="{height}" rx="16"/>
  <text x="40" y="46" class="heading">Code Language Distribution</text>
  <text x="40" y="71" class="subheading">GitHub-detected bytes across active, non-fork public repositories</text>
  {''.join(slices)}
  {''.join(legend)}
</svg>
'''
    LANGUAGE_CHART.parent.mkdir(parents=True, exist_ok=True)
    LANGUAGE_CHART.write_text(svg, encoding="utf-8")


def main():
    repositories = fetch_repositories()
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise RuntimeError("README.md is missing the latest-repositories markers")

    replacement = f"{START}\n{render(repositories)}\n{END}"
    updated = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        lambda _: replacement,
        readme,
        count=1,
        flags=re.DOTALL,
    )
    README.write_text(updated, encoding="utf-8")
    render_language_chart(aggregate_languages(repositories), len(active_projects(repositories)))


if __name__ == "__main__":
    main()
