# GitHub Enterprise client with retries, pagination, branch filtering, last-commit retrieval, and deletion support.
# Important: deletion uses the GitHub Git Refs API: DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}

from __future__ import annotations
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Generator, Optional
from datetime import datetime, timezone
import fnmatch
import urllib.parse

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, host: str, token: str, session: Optional[requests.Session] = None, retry_total: int = 5):
        # Save base host and token, build a session with retries for robustness.
        self.host = host.rstrip("/")                 # normalize host, no trailing slash
        self.token = token

        # Use provided session or create one with robust retry/backoff
        self.session = session or requests.Session()
        retries = Retry(
            total=retry_total,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        # Attach adapter for both http and https
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Common headers (token-based auth)
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "git-copilot-stale-branch-detector/1.0"
        })

    def _request(self, method: str, path: str, params: dict | None = None, json: dict | None = None) -> requests.Response:
        # Internal helper that calls GitHub Enterprise API and raises for non-2xx responses.
        url = f"{self.host}/api/v3{path}"  # GitHub Enterprise typically uses /api/v3
        logger.debug("Requesting %s %s params=%s json=%s", method, url, params, bool(json))
        resp = self.session.request(method, url, params=params, json=json, timeout=30)
        # Raise an HTTPError for non-2xx which will be handled by caller
        resp.raise_for_status()
        return resp

    def list_branches(self, owner: str, repo: str) -> Generator[Dict[str, Any], None, None]:
        # Generator that yields branch objects, transparently handling pagination.
        path = f"/repos/{owner}/{repo}/branches"
        params = {"per_page": 100}
        url_path = path
        while True:
            resp = self._request("GET", url_path, params=params)
            items = resp.json()
            for branch in items:
                yield branch
            # Handle Link header for pagination
            link = resp.headers.get("Link", "")
            next_url = self._parse_next_link(link)
            if not next_url:
                break
            # Convert absolute URL to relative API path expected by _request
            url_path = next_url.replace(self.host, "")
            params = None  # next_url already has query parameters

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        # Extract rel="next" URL from Link header or None if absent.
        if not link_header:
            return None
        parts = link_header.split(",")
        for p in parts:
            if 'rel="next"' in p:
                start = p.find("<") + 1
                end = p.find(">")
                return p[start:end]
        return None

    def is_protected(self, branch_name: str, protected_patterns: List[str]) -> bool:
        # Check whether branch_name matches any protected pattern (supports glob patterns).
        for pat in protected_patterns:
            if fnmatch.fnmatch(branch_name, pat):
                return True
        return False

    def get_commit_date(self, owner: str, repo: str, commit_sha: str) -> datetime:
        # Fetch commit details and extract a timestamp (author.date preferred).
        path = f"/repos/{owner}/{repo}/commits/{commit_sha}"
        resp = self._request("GET", path)
        data = resp.json()
        dt_str = None
        # Prefer commit.author.date then commit.committer.date
        if data.get("commit") and data["commit"].get("author") and data["commit"]["author"].get("date"):
            dt_str = data["commit"]["author"]["date"]
        elif data.get("commit") and data["commit"].get("committer") and data["commit"]["committer"].get("date"):
            dt_str = data["commit"]["committer"]["date"]
        else:
            # If no date is present (unlikely), use now to avoid crash
            logger.warning("Commit %s missing author/committer date; using now()", commit_sha)
            return datetime.now(timezone.utc)
        # Use dateutil parser for robust ISO-8601 parsing
        from dateutil import parser as dateparser
        return dateparser.parse(dt_str)

    def branches_with_last_commit(self, owner: str, repo: str, protected_patterns: List[str]) -> List[dict]:
        # Return list of branch dicts with last commit date attached and filtered (excluding protected branches).
        result = []
        for b in self.list_branches(owner, repo):
            name = b.get("name")
            # Skip protected branches immediately
            if self.is_protected(name, protected_patterns):
                logger.debug("Skipping protected branch %s", name)
                continue
            commit = b.get("commit", {})
            sha = commit.get("sha")
            if not sha:
                logger.warning("Branch %s missing commit SHA; skipping", name)
                continue
            try:
                commit_date = self.get_commit_date(owner, repo, sha)
            except Exception as exc:
                # Log failure and skip; avoids aborting whole run for one problematic branch
                logger.exception("Failed to get commit date for %s@%s: %s", name, sha, exc)
                continue
            result.append({
                "name": name,
                "commit_sha": sha,
                "last_commit_date": commit_date,
            })
        return result

    def delete_branch(self, owner: str, repo: str, branch_name: str) -> None:
        # Delete a branch by removing the git ref: DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}
        # Important: branch_name must be URL-encoded to handle slashes safely.
        # This is irreversible; caller must ensure permissions and confirmations are in place.
        encoded = urllib.parse.quote(branch_name, safe="")  # encode all special chars
        path = f"/repos/{owner}/{repo}/git/refs/heads/{encoded}"
        logger.info("Attempting to delete branch ref %s/%s", repo, branch_name)
        # The API returns 204 No Content on success; raise_for_status will handle non-2xx
        resp = self._request("DELETE", path)
        if resp.status_code not in (204, 200):
            logger.warning("Unexpected response deleting %s: %s", branch_name, resp.status_code)
        else:
            logger.info("Deleted branch %s successfully", branch_name)
