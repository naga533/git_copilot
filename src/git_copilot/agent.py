# AI decision agent for deletion. Contains a deterministic rule-based agent (default)
# and an optional LLM-backed agent that uses OpenAI's chat completion API for a second opinion.
# Safety: AI agent only returns a decision ("delete"/"keep") and a rationale string.

from __future__ import annotations
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class RuleBasedAgent:
    """
    Deterministic decision rules:
    - If branch name contains 'feature/' or starts with 'feat' or 'feature-', candidate for deletion.
    - If branch has no open PRs (not checked here) or hasn't had activity for threshold days, candidate.
    - This agent just returns a boolean and a rationale.
    """
    def decide(self, branch: Dict[str, Any], threshold_days: int) -> Tuple[bool, str]:
        name = branch.get("name", "")
        last_date = branch.get("last_commit_date")
        # Basic heuristic for deciding deletion
        if "wip" in name.lower() or "do-not-delete" in name.lower():
            return False, "Branch marked as WIP / do-not-delete by name"
        # Example: prefer deleting feature/* and feature-*
        if name.startswith("feature/") or name.startswith("feat/") or name.startswith("feature-") or name.startswith("feat-"):
            return True, "Name indicates a feature branch"
        # Default: if older than threshold, candidate
        if last_date:
            return True, f"Last commit older than threshold ({threshold_days} days)"
        return False, "No decisive evidence to delete"

class LLMAgent:
    """
    Optional LLM-backed decision maker. Uses OpenAI Chat API if openai package and key are available.
    It will return (bool decision, rationale).
    WARNING: This should be used as a secondary confirmation step, not the sole safety gate.
    """
    def __init__(self, openai_api_key: Optional[str]):
        self.openai_api_key = openai_api_key
        # Import here so it's optional
        try:
            import openai
            self.openai = openai
            if openai_api_key:
                self.openai.api_key = openai_api_key
        except Exception:
            self.openai = None
            logger.warning("openai package not available or failed to initialize")

    def decide(self, branch: Dict[str, Any], repo_meta: Dict[str, Any], threshold_days: int) -> Tuple[bool, str]:
        # If no openai configured, fallback to neutral (keep).
        if not self.openai or not self.openai_api_key:
            return False, "LLM not configured; defaulting to keep"
        # Build a concise prompt describing the branch
        name = branch.get("name", "")
        last_date = branch.get("last_commit_date")
        commit_sha = branch.get("commit_sha", "")
        prompt = (
            "You are an assistant that recommends whether a git branch should be deleted.\n"
            "Respond with JSON: {\"delete\": true|false, \"rationale\": \"text\"}\n\n"
            f"Repository: {repo_meta.get('owner')}/{repo_meta.get('name')}\n"
            f"Branch: {name}\n"
            f"Last commit: {last_date}\n"
            f"Commit SHA: {commit_sha}\n"
            f"Stale threshold days: {threshold_days}\n\n"
            "Consider branch name conventions and inactivity. If unsure, recommend to KEEP."
        )
        try:
            resp = self.openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.0
            )
            content = resp.choices[0].message.content.strip()
            # Try to parse JSON from the content
            import json
            parsed = json.loads(content)
            return bool(parsed.get("delete")), parsed.get("rationale", "")
        except Exception as exc:
            logger.exception("LLM decision failed: %s", exc)
            # On error, default to KEEP for safety
            return False, f"LLM error: {exc}"
