#!/usr/bin/env python3
"""Update the profile README and its self-hosted GitHub snapshot charts."""

import json
import math
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER = os.getenv("GITHUB_REPOSITORY_OWNER", "mightyalok00")
README = Path("README.md")
ASSETS = Path("assets")
LANGUAGE_CHART = ASSETS / "code-language-distribution.svg"
VOLUME_CHART = ASSETS / "repository-code-volume.svg"
ACTIVITY_CHART = ASSETS / "repository-update-timeline.svg"
START = "<!-- LATEST-REPOS:START -->"
END = "<!-- LATEST-REPOS:END -->"
LIMIT = 6
CHART_LIMIT = 8
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


def fetch_language_data(repositories):
    """Return each active repository with GitHub's detected language-byte totals."""
    return [
        (repo, github_json(repo["languages_url"]))
        for repo in active_projects(repositories)
    ]


def clean(text):
    return " ".join((text or "").replace("|", "\\|").split())


def render_latest_repositories(repositories):
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


def aggregate_languages(language_data):
    totals = {}
    for _, languages in language_data:
        for language, byte_count in languages.items():
            totals[language] = totals.get(language, 0) + byte_count
    return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))


def chart_style():
    return '''
  <style>
    .bg { fill: #ffffff; }
    .heading { fill: #111827; font: 700 24px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .subheading { fill: #6b7280; font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .label { fill: #374151; font: 600 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .value { fill: #111827; font: 700 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .track, .grid { fill: #e5e7eb; stroke: #e5e7eb; }
    @media (prefers-color-scheme: dark) {
      .bg { fill: #0d1117; } .heading, .value { fill: #f0f6fc; }
      .subheading { fill: #8b949e; } .label { fill: #c9d1d9; }
      .track, .grid { fill: #30363d; stroke: #30363d; }
    }
  </style>'''


def svg_document(title, description, height, content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>{chart_style()}
  <rect class="bg" width="800" height="{height}" rx="16"/>
  {content}
</svg>
'''


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
    content = f'''<text x="40" y="46" class="heading">Code Language Distribution</text>
  <text x="40" y="71" class="subheading">GitHub-detected bytes across active, non-fork public repositories</text>
  {''.join(slices)}
  {''.join(legend)}'''
    description = (
        f"Pie chart generated from {repository_count} active, non-fork public repositories "
        "using GitHub language byte totals."
    )
    LANGUAGE_CHART.write_text(
        svg_document(f"{OWNER} code language distribution", description, height, content),
        encoding="utf-8",
    )


def format_bytes(byte_count):
    if byte_count >= 1_000_000:
        return f"{byte_count / 1_000_000:.2f} MB"
    return f"{byte_count / 1_000:.0f} KB"


def render_volume_chart(language_data):
    rows = []
    for repo, languages in language_data:
        byte_count = sum(languages.values())
        if byte_count:
            primary = max(languages, key=languages.get)
            rows.append((repo["name"], byte_count, primary))
    rows.sort(key=lambda row: (-row[1], row[0].lower()))
    rows = rows[:CHART_LIMIT]
    if not rows:
        raise RuntimeError("GitHub returned no repository code-volume data")
    maximum = rows[0][1]
    bars = []
    for index, (name, byte_count, primary) in enumerate(rows):
        y = 105 + index * 44
        width = max(3, 420 * byte_count / maximum)
        color = LANGUAGE_COLORS.get(primary, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])
        bars.append(
            f'<text x="225" y="{y + 16}" class="label" text-anchor="end">{escape(name[:27])}</text>'
            f'<rect x="245" y="{y}" width="420" height="20" rx="6" class="track"/>'
            f'<rect x="245" y="{y}" width="{width:.1f}" height="20" rx="6" fill="{color}">'
            f'<title>{escape(name)}: {byte_count:,} detected bytes</title></rect>'
            f'<text x="745" y="{y + 16}" class="value" text-anchor="end">{format_bytes(byte_count)}</text>'
        )
    height = 145 + len(rows) * 44
    content = f'''<text x="40" y="46" class="heading">Repository Code Volume</text>
  <text x="40" y="71" class="subheading">GitHub-detected code bytes in the largest active public repositories</text>
  {''.join(bars)}'''
    VOLUME_CHART.write_text(
        svg_document(
            f"{OWNER} repository code volume",
            "Horizontal bar chart of GitHub-detected code bytes by public repository.",
            height,
            content,
        ),
        encoding="utf-8",
    )


def parse_github_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def render_activity_chart(repositories):
    rows = [repo for repo in active_projects(repositories) if repo.get("pushed_at")]
    rows.sort(key=lambda repo: repo["pushed_at"], reverse=True)
    rows = rows[:CHART_LIMIT]
    if not rows:
        raise RuntimeError("GitHub returned no repository activity data")
    dates = [parse_github_date(repo["pushed_at"]) for repo in rows]
    earliest, latest = min(dates), max(dates)
    span = max(1, (latest - earliest).total_seconds())
    timeline = []
    for index, (repo, pushed_at) in enumerate(zip(rows, dates)):
        y = 116 + index * 42
        x = 260 + 400 * (pushed_at - earliest).total_seconds() / span
        timeline.append(
            f'<text x="225" y="{y + 5}" class="label" text-anchor="end">{escape(repo["name"][:27])}</text>'
            f'<line x1="260" y1="{y}" x2="660" y2="{y}" class="grid" stroke-width="2"/>'
            f'<circle cx="{x:.1f}" cy="{y}" r="8" fill="#8B5CF6">'
            f'<title>{escape(repo["name"])}: last push {pushed_at:%d %b %Y}</title></circle>'
            f'<text x="745" y="{y + 5}" class="value" text-anchor="end">{pushed_at:%d %b %Y}</text>'
        )
    height = 155 + len(rows) * 42
    content = f'''<text x="40" y="46" class="heading">Recent Project Activity</text>
  <text x="40" y="71" class="subheading">Last push date for the most recently updated public repositories</text>
  <text x="260" y="94" class="subheading">{earliest:%d %b %Y}</text>
  <text x="660" y="94" class="subheading" text-anchor="end">{latest:%d %b %Y}</text>
  {''.join(timeline)}'''
    ACTIVITY_CHART.write_text(
        svg_document(
            f"{OWNER} recent project activity",
            "Timeline of the last push date for recently updated public repositories.",
            height,
            content,
        ),
        encoding="utf-8",
    )


def main():
    repositories = fetch_repositories()
    language_data = fetch_language_data(repositories)
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise RuntimeError("README.md is missing the latest-repositories markers")
    replacement = f"{START}\n{render_latest_repositories(repositories)}\n{END}"
    updated = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        lambda _: replacement,
        readme,
        count=1,
        flags=re.DOTALL,
    )
    README.write_text(updated, encoding="utf-8")
    ASSETS.mkdir(parents=True, exist_ok=True)
    render_language_chart(aggregate_languages(language_data), len(language_data))
    render_volume_chart(language_data)
    render_activity_chart(repositories)


if __name__ == "__main__":
    main()
