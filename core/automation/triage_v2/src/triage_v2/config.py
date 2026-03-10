from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_STATE_DIR = ROOT / "core" / "state" / "email-triage-v2"
DEFAULT_CORE_STATE_DIR = ROOT / "core" / "state"
DEFAULT_RUNTIME_PERSONAL_ROOT = Path.home() / "Projects" / "automation-runtime-personal"


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    artifact_dir: Path
    outbox_dir: Path
    fixture_dir: Path
    provider_mode: str
    sender_mode: str
    draft_mode: str
    superhuman_script_path: Path
    gmail_work_home: Path
    gmail_personal_home: Path
    default_work_account: str
    default_personal_account: str
    enabled_accounts: tuple[str, ...]
    digest_to: str
    digest_sender_account: str
    coverage_target: float
    send_target: float
    projects_dir: Path
    goals_path: Path
    people_path: Path
    email_contacts_path: Path
    email_drafting_policy_path: Path
    writing_style_path: Path
    comms_events_path: Path
    granola_sync_state_path: Path
    project_refresh_state_path: Path
    meeting_sync_fetch_path: Path
    claude_path: Path
    draft_authoring_mode: str
    draft_authoring_provider: str
    draft_authoring_model: str
    draft_authoring_timeout_seconds: int
    project_refresh_provider: str
    project_refresh_model: str
    project_refresh_timeout_seconds: int
    project_refresh_batch_size: int
    project_refresh_max_source_items: int
    project_refresh_stale_hours: int


def load_config() -> AppConfig:
    state_dir = Path(os.environ.get("TRIAGE_V2_STATE_DIR", str(DEFAULT_STATE_DIR))).resolve()
    artifact_dir = Path(os.environ.get("TRIAGE_V2_ARTIFACT_DIR", str(state_dir / "artifacts"))).resolve()
    outbox_dir = Path(os.environ.get("TRIAGE_V2_OUTBOX_DIR", str(state_dir / "outbox"))).resolve()
    fixture_dir = Path(
        os.environ.get(
            "TRIAGE_V2_FIXTURE_DIR",
            str(ROOT / "core" / "automation" / "triage_v2" / "fixtures"),
        )
    ).resolve()
    superhuman_script = Path(
        os.environ.get(
            "TRIAGE_V2_SUPERHUMAN_SCRIPT",
            str(ROOT / "core" / "automation" / "superhuman-draft.sh"),
        )
    ).resolve()
    gmail_work_home = Path(os.environ.get("TRIAGE_V2_GMAIL_WORK_HOME", str(Path.home() / ".gmail-mcp"))).resolve()
    gmail_personal_home = Path(
        os.environ.get("TRIAGE_V2_GMAIL_PERSONAL_HOME", str(Path.home() / ".gmail-mcp-personal"))
    ).resolve()
    db_path = Path(os.environ.get("TRIAGE_V2_DB_PATH", str(state_dir / "triage-v2.db"))).resolve()
    raw_accounts = os.environ.get("TRIAGE_V2_ACCOUNTS", "work,personal")
    enabled_accounts = tuple(
        account for account in ("work", "personal") if account in {a.strip().lower() for a in raw_accounts.split(",")}
    )
    if not enabled_accounts:
        enabled_accounts = ("work",)

    return AppConfig(
        db_path=db_path,
        artifact_dir=artifact_dir,
        outbox_dir=outbox_dir,
        fixture_dir=fixture_dir,
        provider_mode=os.environ.get("TRIAGE_V2_PROVIDER_MODE", "file").strip().lower(),
        sender_mode=os.environ.get("TRIAGE_V2_SENDER_MODE", "local_outbox").strip().lower(),
        draft_mode=os.environ.get("TRIAGE_V2_DRAFT_MODE", "superhuman_preferred").strip().lower(),
        superhuman_script_path=superhuman_script,
        gmail_work_home=gmail_work_home,
        gmail_personal_home=gmail_personal_home,
        default_work_account=os.environ.get("TRIAGE_V2_WORK_ACCOUNT", "matt@cornerboothholdings.com"),
        default_personal_account=os.environ.get("TRIAGE_V2_PERSONAL_ACCOUNT", "lieber.matt@gmail.com"),
        enabled_accounts=enabled_accounts,
        digest_to=os.environ.get("TRIAGE_V2_DIGEST_TO", "matt@cornerboothholdings.com"),
        digest_sender_account=os.environ.get("TRIAGE_V2_DIGEST_SENDER_ACCOUNT", "work").strip().lower(),
        coverage_target=float(os.environ.get("TRIAGE_V2_COVERAGE_TARGET", "99.9")),
        send_target=float(os.environ.get("TRIAGE_V2_SEND_TARGET", "99.5")),
        projects_dir=Path(os.environ.get("TRIAGE_V2_PROJECTS_DIR", str(ROOT / "projects"))).resolve(),
        goals_path=Path(os.environ.get("TRIAGE_V2_GOALS_PATH", str(ROOT / "GOALS.md"))).resolve(),
        people_path=Path(os.environ.get("TRIAGE_V2_PEOPLE_PATH", str(ROOT / "core" / "context" / "people.md"))).resolve(),
        email_contacts_path=Path(
            os.environ.get(
                "TRIAGE_V2_EMAIL_CONTACTS_PATH",
                str(ROOT / "core" / "context" / "email-contacts.md"),
            )
        ).resolve(),
        email_drafting_policy_path=Path(
            os.environ.get(
                "TRIAGE_V2_EMAIL_DRAFTING_POLICY_PATH",
                str(ROOT / "core" / "policies" / "email-drafting.md"),
            )
        ).resolve(),
        writing_style_path=Path(
            os.environ.get(
                "TRIAGE_V2_WRITING_STYLE_PATH",
                str(ROOT / "core" / "context" / "writing-style.md"),
            )
        ).resolve(),
        comms_events_path=Path(
            os.environ.get(
                "TRIAGE_V2_COMMS_EVENTS_PATH",
                str(DEFAULT_CORE_STATE_DIR / "comms-events.jsonl"),
            )
        ).resolve(),
        granola_sync_state_path=Path(
            os.environ.get(
                "TRIAGE_V2_GRANOLA_SYNC_STATE_PATH",
                str(DEFAULT_CORE_STATE_DIR / "granola-sync.json"),
            )
        ).resolve(),
        project_refresh_state_path=Path(
            os.environ.get(
                "TRIAGE_V2_PROJECT_REFRESH_STATE_PATH",
                str(DEFAULT_CORE_STATE_DIR / "project-refresh-state.json"),
            )
        ).resolve(),
        meeting_sync_fetch_path=Path(
            os.environ.get(
                "TRIAGE_V2_MEETING_SYNC_FETCH_PATH",
                str(DEFAULT_RUNTIME_PERSONAL_ROOT / "core" / "automation" / "meeting-sync-fetch.py"),
            )
        ).resolve(),
        claude_path=Path(
            os.environ.get(
                "TRIAGE_V2_CLAUDE_PATH",
                str(Path.home() / ".local" / "bin" / "claude"),
            )
        ).resolve(),
        draft_authoring_mode=os.environ.get("TRIAGE_V2_DRAFT_AUTHORING_MODE", "llm_with_fallback").strip().lower(),
        draft_authoring_provider=os.environ.get("TRIAGE_V2_DRAFT_AUTHORING_PROVIDER", "claude_cli").strip().lower(),
        draft_authoring_model=os.environ.get("TRIAGE_V2_DRAFT_AUTHORING_MODEL", "sonnet").strip(),
        draft_authoring_timeout_seconds=int(os.environ.get("TRIAGE_V2_DRAFT_AUTHORING_TIMEOUT_SECONDS", "45")),
        project_refresh_provider=os.environ.get("TRIAGE_V2_PROJECT_REFRESH_PROVIDER", "claude_cli").strip().lower(),
        project_refresh_model=os.environ.get("TRIAGE_V2_PROJECT_REFRESH_MODEL", "sonnet").strip(),
        project_refresh_timeout_seconds=int(os.environ.get("TRIAGE_V2_PROJECT_REFRESH_TIMEOUT_SECONDS", "120")),
        project_refresh_batch_size=int(os.environ.get("TRIAGE_V2_PROJECT_REFRESH_BATCH_SIZE", "8")),
        project_refresh_max_source_items=int(os.environ.get("TRIAGE_V2_PROJECT_REFRESH_MAX_SOURCE_ITEMS", "64")),
        project_refresh_stale_hours=int(os.environ.get("TRIAGE_V2_PROJECT_REFRESH_STALE_HOURS", "12")),
    )


def ensure_directories(cfg: AppConfig) -> None:
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
    cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
    cfg.project_refresh_state_path.parent.mkdir(parents=True, exist_ok=True)
