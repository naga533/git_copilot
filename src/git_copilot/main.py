# CLI entrypoint. Orchestrates configuration, GitHub calls, decisioning (AI/rule), safe deletion,
# reporting, emailing, and auditing. Safeguards: dry-run default and explicit confirmation required for deletes.

from __future__ import annotations
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
import click
from typing import List

from .config import Settings
from .logging_config import configure_logging
from .github_client import GitHubClient
from .report import generate_reports
from .emailer import send_email_smtp
from .audit import AuditLogger
from .agent import RuleBasedAgent, LLMAgent

logger = logging.getLogger(__name__)

@click.command()
@click.option("--config-file", default=None, help="Path to YAML config file (optional).")
@click.option("--confirm-delete", is_flag=True, default=False, help="Explicit flag to confirm deletions (required if REQUIRE_CONFIRM_FLAG set).")
def run(config_file, confirm_delete):
    # 1) Load configuration (env + optional config file)
    os.environ["CONFIG_FILE"] = config_file or os.environ.get("CONFIG_FILE", "")  # allow CLI override
    settings = Settings.load()

    # 2) Configure logging
    os.makedirs("logs", exist_ok=True)
    configure_logging(settings.log_level, logfile="logs/app.log")
    logger.info("Starting stale branch detection job (dry_run=%s)", settings.dry_run)

    # 3) Initialize AuditLogger
    audit = AuditLogger(jsonl_path=settings.audit_jsonl_path, sqlite_path=settings.audit_sqlite_path)
    audit.record("run_started", {"repo": f"{settings.repo_owner}/{settings.repo_name}", "dry_run": settings.dry_run})

    # 4) Validate deletion safety flags before doing any destructive action
    if settings.require_confirm_flag and confirm_delete is False and settings.allow_deletes:
        logger.error("Deletion requested (ALLOW_DELETES=true) but --confirm-delete flag not provided. Aborting deletion capability.")
        audit.record("deletion_aborted_missing_confirm", {"allow_deletes": settings.allow_deletes, "require_confirm_flag": settings.require_confirm_flag})
        # Keep running in dry-run mode but prevent deletes
        settings.allow_deletes = False

    # 5) Init GitHub client
    try:
        gh = GitHubClient(settings.ghe_host, settings.ghe_token)
    except Exception as exc:
        logger.exception("Failed to initialize GitHub client")
        audit.record("run_failed", {"reason": "init_client", "error": str(exc)})
        sys.exit(1)

    # 6) Fetch branches (non-protected)
    try:
        all_branches = gh.branches_with_last_commit(settings.repo_owner, settings.repo_name, settings.protected_branches)
        audit.record("branches_fetched", {"count": len(all_branches)})
    except Exception as exc:
        logger.exception("Failed to fetch branches")
        audit.record("run_failed", {"reason": "fetch_branches", "error": str(exc)})
        sys.exit(1)

    # 7) Determine stale threshold and candidates
    threshold_dt = datetime.now(timezone.utc) - timedelta(days=settings.branch_stale_days)
    stale_candidates = []
    for b in all_branches:
        last_date = b.get("last_commit_date")
        if last_date and last_date < threshold_dt:
            stale_candidates.append(b)

    logger.info("Found %d stale branch candidates (older than %d days)", len(stale_candidates), settings.branch_stale_days)
    audit.record("stale_candidates_identified", {"count": len(stale_candidates)})

    # 8) Initialize agents: rule-based always available; LLM optional
    rule_agent = RuleBasedAgent()
    llm_agent = None
    if settings.use_ai and settings.openai_api_key:
        llm_agent = LLMAgent(settings.openai_api_key)

    to_delete: List[dict] = []
    kept: List[dict] = []

    # 9) Decide for each stale candidate whether to delete (AI or rules)
    for branch in stale_candidates:
        # Use rule-based decision first
        rule_decision, rule_rationale = rule_agent.decide(branch, settings.branch_stale_days)
        decision = rule_decision
        rationale = f"RuleAgent: {rule_rationale}"

        # If LLM configured, ask for a second opinion (LLM should NOT be sole safety mechanism)
        if llm_agent:
            llm_decision, llm_rationale = llm_agent.decide(branch, {"owner": settings.repo_owner, "name": settings.repo_name}, settings.branch_stale_days)
            # Combine decisions: require both agents to agree to delete (conservative)
            if decision and llm_decision:
                decision = True
                rationale += f"; LLMAgent: {llm_rationale}"
            else:
                # If disagreement, default to KEEP but include both rationales
                decision = False
                rationale += f"; LLMAgent: {llm_rationale} (keeps by default on disagreement)"
        # Append to lists for later action
        if decision:
            to_delete.append({"branch": branch, "rationale": rationale})
        else:
            kept.append({"branch": branch, "rationale": rationale})

        # Audit each decision
        audit.record("deletion_decision", {
            "branch": branch.get("name"),
            "decision": "delete" if decision else "keep",
            "rationale": rationale
        })

    logger.info("Decision: %d to delete, %d to keep", len(to_delete), len(kept))

    # 10) Perform deletions if allowed and not dry-run
    deleted = []
    failed_deletes = []
    for item in to_delete:
        b = item["branch"]
        name = b["name"]
        if not settings.allow_deletes or settings.dry_run:
            # Dry-run or deletes not allowed: do not delete, just log
            logger.info("[DRY-RUN] Would delete branch: %s (%s)", name, item["rationale"])
            continue
        try:
            gh.delete_branch(settings.repo_owner, settings.repo_name, name)
            deleted.append({"name": name, "commit_sha": b.get("commit_sha"), "rationale": item["rationale"]})
            audit.record("branch_deleted", {"branch": name, "commit_sha": b.get("commit_sha")})
        except Exception as exc:
            logger.exception("Failed to delete branch %s: %s", name, exc)
            failed_deletes.append({"name": name, "error": str(exc)})
            audit.record("delete_failed", {"branch": name, "error": str(exc)})

    # 11) Generate reports summarizing decisions and deletions
    # Build lists in the format report.generate_reports expects (list of dicts)
    all_branches_info = [{
        "name": b["name"],
        "commit_sha": b["commit_sha"],
        "last_commit_date": b["last_commit_date"],
    } for b in all_branches]

    stale_branches_info = [{
        "name": b["name"],
        "commit_sha": b["commit_sha"],
        "last_commit_date": b["last_commit_date"],
    } for b in stale_candidates]

    report_paths = generate_reports(settings.output_dir, settings.repo_owner, settings.repo_name, all_branches_info, stale_branches_info, formats=["json", "csv", "markdown"])
    audit.record("reports_written", {"paths": report_paths})

    # 12) Send summary email
    if settings.smtp_host and settings.email_to:
        subject = f"Stale branches report for {settings.repo_owner}/{settings.repo_name}"
        body_lines = [
            f"Stale branch candidates: {len(stale_candidates)}",
            f"Planned deletions (decisioned): {len(to_delete)}",
            f"Deleted (performed): {len(deleted)}",
            f"Failed deletions: {len(failed_deletes)}",
            "",
            "Details:",
            "Deleted:",
        ]
        for d in deleted:
            body_lines.append(f"- {d['name']} ({d['commit_sha']}) rationale: {d['rationale']}")
        body_lines.append("")
        body_lines.append("Kept:")
        for k in kept:
            body_lines.append(f"- {k['branch']['name']} rationale: {k['rationale']}")
        body = "\n".join(body_lines)

        try:
            attachments = [report_paths["detailed"]]
            csv_path = os.path.join(settings.output_dir, "stale_branches.csv")
            if os.path.exists(csv_path):
                attachments.append(csv_path)
            send_email_smtp(
                host=settings.smtp_host,
                port=settings.smtp_port or 587,
                username=settings.smtp_username,
                password=settings.smtp_password,
                sender=settings.email_from,
                recipients=[x.strip() for x in settings.email_to.split(",")],
                subject=subject,
                body=body,
                attachments=attachments
            )
            audit.record("email_sent", {"to": settings.email_to, "attachments": attachments})
        except Exception:
            logger.exception("Failed to send email")
            audit.record("email_failed", {"error": "email send exception"})
    else:
        logger.info("Email settings not configured; skipping email send")

    audit.record("run_completed", {
        "stale_candidates": len(stale_candidates),
        "to_delete": len(to_delete),
        "deleted": len(deleted),
        "failed_deletes": len(failed_deletes),
    })
    logger.info("Run completed. Deleted: %d. Failed: %d", len(deleted), len(failed_deletes))
