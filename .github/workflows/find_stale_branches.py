#!/usr/bin/env python3
"""
Stale Feature Branch Finder
----------------------------
Scans all branches in a GitHub repository and reports "feature" branches
(i.e. everything except main/master/develop and release/*) whose last
commit is older than a configurable threshold (default: 30 days).

Usage:
    export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    python find_stale_branches.py --repo owner/repo-name
    python find_stale_branches.py --repo owner/repo-name --days 45 --format json

Requirements:
    pip install requests --break-system-packages
"""

import argparse
import fnmatch
import json
import os
import sys
from datetime import datetime, timezone

import requests

GITHUB_API = "https://api.github.com"

# Branches that are never considered "feature" branches, even if they don't
# match a name pattern below.
DEFAULT_EXCLUDE_PATTERNS = [
    "main",
    "master",
    "develop",
    "release/*",
]


def is_excluded(branch_name: str, exclude_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(branch_name, pattern) for pattern in exclude_patterns)


def github_get(url: str, token: str, params: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 404:
        raise SystemExit(f"Repo not found or no access: {url}")
    if resp.status_code == 401:
        raise SystemExit("Bad or missing GITHUB_TOKEN — authentication failed.")
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise SystemExit("GitHub API rate limit hit. Use a token with a higher limit.")
    resp.raise_for_status()
    return resp


def list_branches(repo: str, token: str):
    """Yield every branch name in the repo (paginated)."""
    url = f"{GITHUB_API}/repos/{repo}/branches"
    page = 1
    while True:
        resp = github_get(url, token, params={"per_page": 100, "page": page})
        data = resp.json()
        if not data:
            break
        for b in data:
            yield b["name"]
        page += 1


def get_last_commit_date(repo: str, branch: str, token: str) -> datetime:
    """Return the timestamp of the last commit on a branch."""
    url = f"{GITHUB_API}/repos/{repo}/commits/{branch}"
    resp = github_get(url, token)
    data = resp.json()
    date_str = data["commit"]["committer"]["date"]  # ISO 8601, e.g. 2025-01-01T12:00:00Z
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def find_stale_branches(repo: str, token: str, days_threshold: int, exclude_patterns: list[str]):
    now = datetime.now(timezone.utc)
    results = []

    all_branches = list(list_branches(repo, token))
    candidate_branches = [b for b in all_branches if not is_excluded(b, exclude_patterns)]

    for branch in candidate_branches:
        last_commit_date = get_last_commit_date(repo, branch, token)
        age_days = (now - last_commit_date).days
        if age_days >= days_threshold:
            results.append(
                {
                    "branch": branch,
                    "last_commit_date": last_commit_date.strftime("%Y-%m-%d"),
                    "inactive_days": age_days,
                }
            )

    results.sort(key=lambda r: r["inactive_days"], reverse=True)
    return results, len(all_branches), len(candidate_branches)


def print_table(results):
    if not results:
        print("No stale feature branches found.")
        return
    name_w = max(len("Branch"), max(len(r["branch"]) for r in results))
    print(f"{'Branch'.ljust(name_w)}  {'Last Commit'.ljust(12)}  Inactive Days")
    print("-" * (name_w + 12 + 18))
    for r in results:
        print(f"{r['branch'].ljust(name_w)}  {r['last_commit_date'].ljust(12)}  {r['inactive_days']}")


def main():
    parser = argparse.ArgumentParser(description="Find inactive feature branches in a GitHub repo.")
    parser.add_argument("--repo", required=True, help="owner/repo-name, e.g. octocat/hello-world")
    parser.add_argument("--days", type=int, default=30, help="Inactivity threshold in days (default: 30)")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=DEFAULT_EXCLUDE_PATTERNS,
        help="Branch name patterns to exclude (glob-style). Default: main master develop release/*",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token. Defaults to $GITHUB_TOKEN env var.",
    )
    args = parser.parse_args()

    if not args.token:
        print(
            "Warning: no GITHUB_TOKEN set. This will work for public repos but hit low rate limits.",
            file=sys.stderr,
        )

    results, total_branches, candidate_count = find_stale_branches(
        args.repo, args.token, args.days, args.exclude
    )

    if args.format == "json":
        print(json.dumps(results, indent=2))
    else:
        print(f"Repo: {args.repo}")
        print(f"Total branches: {total_branches} | Candidate (non-excluded) branches: {candidate_count}")
        print(f"Threshold: {args.days}+ days inactive")
        print(f"Excluded patterns: {', '.join(args.exclude)}\n")
        print_table(results)


if __name__ == "__main__":
    main()
