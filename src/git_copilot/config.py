# Configuration handling using pydantic BaseSettings for environment variables and YAML file support.
# Important: every setting comes from environment variables or an optional config file.

from __future__ import annotations
import os
import yaml
from typing import List, Optional
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    # GitHub Enterprise
    ghe_host: str = Field(..., env="GHE_HOST")            # e.g. https://ghe.example.com
    ghe_token: str = Field(..., env="GHE_TOKEN")          # PAT with repo access
    repo_owner: str = Field(..., env="GHE_REPO_OWNER")    # repository owner/org
    repo_name: str = Field(..., env="GHE_REPO_NAME")      # repository name

    # Protected branch patterns (glob support)
    protected_branches: List[str] = Field(default_factory=lambda: ["main","master","develop","release/*","hotfix/*"])

    # Stale threshold in days
    branch_stale_days: int = Field(30, env="BRANCH_STALE_DAYS")

    # Deletion controls & safety
    allow_deletes: bool = Field(False, env="ALLOW_DELETES")    # global toggle; default OFF
    dry_run: bool = Field(True, env="DRY_RUN")                 # default True
    require_confirm_flag: bool = Field(True, env="REQUIRE_CONFIRM_FLAG")  # if true, CLI must pass --confirm-delete

    # AI decisioning (optional)
    use_ai: bool = Field(False, env="USE_AI")              # if True, uses LLM to assist decisions
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")  # OpenAI key if using LLM

    # Output and logging
    output_dir: str = Field("./outputs", env="OUTPUT_DIR")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # Email (SMTP)
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: Optional[int] = Field(None, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(None, env="SMTP_PASSWORD")
    email_from: Optional[str] = Field(None, env="EMAIL_FROM")
    email_to: Optional[str] = Field(None, env="EMAIL_TO")

    # Audit
    audit_sqlite_path: str = Field("./data/audit.db", env="AUDIT_SQLITE_PATH")
    audit_jsonl_path: str = Field("./data/audit.jsonl", env="AUDIT_JSONL_PATH")

    # Config file (optional YAML)
    config_file: Optional[str] = Field(None, env="CONFIG_FILE")

    class Config:
        env_file = ".env"  # allow local .env usage

    @classmethod
    def load(cls) -> "Settings":
        # Load environment-first settings then overlay config file if present
        base = cls()  # loads from environment variables and .env
        cfg_path = base.config_file or os.environ.get("CONFIG_FILE")
        if cfg_path and os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            # overlay protected branches if present
            if "protected_branches" in cfg:
                base.protected_branches = cfg["protected_branches"]
            # other overlay options can be added here
        return base
