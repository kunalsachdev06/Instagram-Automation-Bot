from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from bot.utils import append_jsonl, load_json, read_jsonl_ids, save_json_atomic


class FollowerScraper:
    """Scrape followers in batches with checkpointing."""

    def __init__(self, client: Any, settings: Any, logger: Any) -> None:
        self._client = client
        self._settings = settings
        self._logger = logger

    def scrape_followers(self, target_username: str, resume: bool = True) -> Path:
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

        try:
            usernames = self._client.get_followers(target_username)
        except Exception as exc:
            self._logger.error(
                "Failed to scrape followers",
                extra={"target": target_username, "error": str(exc)},
            )
            raise

        new_count = 0
        for username in usernames:
            entry_id = str(username)
            if not entry_id or entry_id in seen_ids:
                continue
            append_jsonl(
                followers_path,
                {"id": entry_id, "username": entry_id, "full_name": ""},
            )
            seen_ids.add(entry_id)
            new_count += 1

        total_saved += new_count
        save_json_atomic(
            progress_path,
            {
                "total_saved": total_saved,
            },
        )

        self._logger.info(
            "Batch saved",
            extra={"new": new_count, "total": total_saved},
        )

        self._logger.info("Scrape complete", extra={"total": total_saved})
        return followers_path
