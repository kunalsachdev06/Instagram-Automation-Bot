from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from bot.utils import (
    append_jsonl,
    build_retryable_exceptions,
    is_rate_limited_429,
    is_retryable_exception,
    normalize_user,
    read_jsonl_ids,
    sleep_with_jitter,
    stream_jsonl,
)


class ActionRunner:
    """Follow and DM users with rate-limit safety and resume support."""

    def __init__(self, client: Any, settings: Any, logger: Any) -> None:
        self._client = client
        self._settings = settings
        self._logger = logger
        self._retryable = build_retryable_exceptions()

    def follow_and_message(
        self,
        followers_path: Path,
        message: str,
        max_actions: int,
        dry_run: bool,
    ) -> None:
        data_dir = Path(self._settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        done_path = data_dir / "actions_done.jsonl"
        done_ids = read_jsonl_ids(done_path)

        action_count = 0
        for entry in stream_jsonl(followers_path):
            user = normalize_user(entry)
            if user["id"] in done_ids:
                continue
            if action_count >= max_actions:
                break

            if dry_run:
                self._logger.info(
                    "Dry-run",
                    extra={"user": user["username"], "id": user["id"]},
                )
                continue

            try:
                self._follow_user(user["id"])
                sleep_with_jitter(self._settings.min_delay, self._settings.max_delay)
                self._send_dm(user["id"], message)
            except Exception as exc:
                if is_rate_limited_429(exc):
                    self._logger.error(
                        "Rate limited (429) during action; stopping",
                        extra={"user": user["username"], "error": str(exc)},
                    )
                    raise
                self._logger.error(
                    "Action failed",
                    extra={"user": user["username"], "error": str(exc)},
                )
                sleep_with_jitter(self._settings.cooldown_min, self._settings.cooldown_max)
                continue

            action_count += 1
            done_ids.add(user["id"])
            append_jsonl(
                done_path,
                {
                    "id": user["id"],
                    "username": user["username"],
                    "status": "followed_and_messaged",
                },
            )

            self._logger.info(
                "Action complete",
                extra={"user": user["username"], "count": action_count},
            )

            if action_count % self._settings.cooldown_every == 0:
                sleep_with_jitter(self._settings.cooldown_min, self._settings.cooldown_max)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        wait=wait_exponential_jitter(initial=5, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _follow_user(self, username: str) -> None:
        self._client.follow_user(username)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        wait=wait_exponential_jitter(initial=5, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _send_dm(self, username: str, message: str) -> None:
        self._client.send_dm(username, message)
