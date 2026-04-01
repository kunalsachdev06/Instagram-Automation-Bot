from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import os


@dataclass(frozen=True)
class Settings:
    ig_username: str
    ig_password: str
    session_path: str
    data_dir: str
    logs_dir: str
    log_level: str
    initial_post_login_delay: int
    min_delay: int
    max_delay: int
    cooldown_every: int
    cooldown_min: int
    cooldown_max: int
    max_actions: int
    batch_size: int
    message_template: str
    dry_run: bool
    proxy: str
    user_agent: str


def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")

    ig_username = os.getenv("IG_USERNAME", "")
    default_session_name = "session.json"
    if ig_username:
        default_session_name = f"session_{ig_username}.json"

    return Settings(
        ig_username=ig_username,
        ig_password=os.getenv("IG_PASSWORD", ""),
        session_path=os.getenv(
            "IG_SESSION_PATH",
            str(root / "data" / default_session_name),
        ),
        data_dir=os.getenv("DATA_DIR", str(root / "data")),
        logs_dir=os.getenv("LOGS_DIR", str(root / "logs")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        initial_post_login_delay=int(os.getenv("INITIAL_POST_LOGIN_DELAY", "45")),
        min_delay=int(os.getenv("MIN_DELAY", "8")),
        max_delay=int(os.getenv("MAX_DELAY", "25")),
        cooldown_every=int(os.getenv("COOLDOWN_EVERY", "30")),
        cooldown_min=int(os.getenv("COOLDOWN_MIN", "60")),
        cooldown_max=int(os.getenv("COOLDOWN_MAX", "120")),
        max_actions=int(os.getenv("MAX_ACTIONS", "150")),
        batch_size=int(os.getenv("BATCH_SIZE", "200")),
        message_template=os.getenv("DM_MESSAGE", "Check out our services"),
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        proxy=os.getenv("IG_PROXY", ""),
        user_agent=os.getenv("IG_USER_AGENT", ""),
    )


def override_settings(
    settings: Settings,
    message: Optional[str] = None,
    max_actions: Optional[int] = None,
    batch_size: Optional[int] = None,
    dry_run: Optional[bool] = None,
) -> Settings:
    return replace(
        settings,
        message_template=message or settings.message_template,
        max_actions=max_actions if max_actions is not None else settings.max_actions,
        batch_size=batch_size if batch_size is not None else settings.batch_size,
        dry_run=dry_run if dry_run is not None else settings.dry_run,
    )
