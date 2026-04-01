from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from bot.utils import (
    append_jsonl,
    is_rate_limited_429,
    load_json,
    normalize_user,
    read_jsonl_ids,
    save_json_atomic,
)


class FollowerScraper:
    """Scrape followers in batches with checkpointing."""

    def __init__(self, client: Any, settings: Any, logger: Any) -> None:
        self._client = client
        self._settings = settings
        self._logger = logger

    def scrape_followers(self, target_username: str, resume: bool = True) -> Path:
        user_id = None
        data_dir = Path(self._settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        followers_path = data_dir / f"followers_{target_username}.jsonl"
        progress_path = data_dir / f"followers_{target_username}_progress.json"

        if not resume:
            if followers_path.exists():
                followers_path.unlink()
            if progress_path.exists():
                progress_path.unlink()

        progress: Dict[str, Any] = load_json(progress_path, default={})
        cached_user_id = progress.get("user_id")
        if cached_user_id:
            user_id = int(cached_user_id)
        else:
            try:
                user_id = self._client.user_id_from_username(target_username)
            except Exception as exc:
                if is_rate_limited_429(exc):
                    self._logger.error(
                        "Rate limited (429) during user lookup; stopping",
                        extra={"target": target_username, "error": str(exc)},
                    )
                raise
            progress["user_id"] = user_id
            save_json_atomic(progress_path, progress)
        max_id: Optional[str] = progress.get("max_id")

        seen_ids = read_jsonl_ids(followers_path)
        total_saved = len(seen_ids)
        self._logger.info(
            "Starting scrape",
            extra={
                "target": target_username,
                "saved": total_saved,
                "resume": resume,
            },
        )

        while True:
            try:
                users, next_max_id = self._client.fetch_followers_batch(
                    user_id, max_id=max_id, batch_size=self._settings.batch_size
                )
            except Exception as exc:
                if is_rate_limited_429(exc):
                    self._logger.error(
                        "Rate limited (429) during scrape; stopping",
                        extra={"target": target_username, "error": str(exc)},
                    )
                raise
            if not users:
                break

            new_count = 0
            for user in users:
                entry = normalize_user(user)
                if not entry["id"] or entry["id"] in seen_ids:
                    continue
                append_jsonl(followers_path, entry)
                seen_ids.add(entry["id"])
                new_count += 1

            total_saved += new_count
            max_id = next_max_id
            save_json_atomic(
                progress_path,
                {
                    "max_id": max_id,
                    "total_saved": total_saved,
                },
            )

            self._logger.info(
                "Batch saved",
                extra={"new": new_count, "total": total_saved, "next": bool(max_id)},
            )

            if not max_id:
                break

        self._logger.info("Scrape complete", extra={"total": total_saved})
        return followers_path
