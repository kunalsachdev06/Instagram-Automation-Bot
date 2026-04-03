from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bot.actions import ActionRunner
from bot.selenium_client import SeleniumInstagramClient
from bot.scraper import FollowerScraper
from bot.utils import configure_logging
from config.settings import load_settings, override_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Instagram automation bot (educational demo only)."
    )
    parser.add_argument("target_username", help="Public Instagram username to scrape")
    parser.add_argument("--message", help="DM message text to send")
    parser.add_argument("--max-actions", type=int, help="Max follow+DM actions per run")
    parser.add_argument("--batch-size", type=int, help="Followers to fetch per batch")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, no follow/DM")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing progress")
    parser.add_argument(
        "--followers-path",
        type=Path,
        help="Use an existing followers JSONL file instead of scraping",
    )
    return parser


def main() -> None:
    print(f"__file__: {__file__}")
    print(f"cwd: {os.getcwd()}")
    print(f"python: {sys.executable}")
    parser = build_parser()
    args = parser.parse_args()

    settings = load_settings()
    settings = override_settings(
        settings,
        message=args.message,
        max_actions=args.max_actions,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    logger = configure_logging(settings.log_level, settings.logs_dir)
    logger.info("Starting run", extra={"target": args.target_username})

    client = SeleniumInstagramClient(settings, logger)
    client.login()

    followers_path = args.followers_path
    if followers_path is None:
        scraper = FollowerScraper(client, settings, logger)
        followers_path = scraper.scrape_followers(
            args.target_username,
            resume=not args.no_resume,
        )

    runner = ActionRunner(client, settings, logger)
    runner.follow_and_message(
        followers_path,
        message=settings.message_template,
        max_actions=settings.max_actions,
        dry_run=settings.dry_run,
    )

    logger.info("Run complete")


if __name__ == "__main__":
    main()
