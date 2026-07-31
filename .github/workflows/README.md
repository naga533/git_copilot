# Stale Feature Branch Finder

Scans a GitHub repo and lists feature branches with no commits in 30+ days.

Excludes by default: `main`, `master`, `develop`, `release/*` (everything else counts as a "feature" branch).

## Option 1 — Run locally

```bash
pip install requests --break-system-packages

export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx   # needs 'repo' scope for private repos
python find_stale_branches.py --repo your-org/your-repo
```

Useful flags:
- `--days 45` — change the inactivity threshold
- `--format json` — machine-readable output
- `--exclude main master develop "release/*" "hotfix/*"` — customize what's excluded

## Option 2 — Run automatically on a schedule (GitHub Action)

1. Move `.github_workflows_stale-branches.yml` into your repo at:
   `.github/workflows/stale-branches.yml`
2. Also add `find_stale_branches.py` to the repo root (or adjust the path in the workflow).
3. Commit and push. It will run every Monday at 6 AM UTC, or anytime from the
   Actions tab via "Run workflow."
4. Results land as a downloadable artifact (`stale-branch-report`) on each run.
   Uncomment the last step in the workflow if you'd rather it post the report
   as a GitHub issue automatically.

No extra secret setup needed for public repos in the same org — the built-in
`secrets.GITHUB_TOKEN` GitHub provides to every workflow run is enough to read
branches and commits.

## How "inactive" is measured

For each branch (excluding the patterns above), the script fetches the
timestamp of its most recent commit and compares it to now. Branches at or
past the threshold are reported, sorted by longest-inactive first.
