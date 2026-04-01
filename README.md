# Instagram Automation Bot
Reliable, rate-limit aware Instagram automation for educational demonstrations.

**WARNING / DISCLAIMER (READ FIRST)**

**AUTOMATION VIOLATES INSTAGRAM TERMS OF SERVICE.**
**YOU CAN BE RATE-LIMITED, CHALLENGED, OR PERMANENTLY BANNED.**
**EDUCATIONAL DEMONSTRATION ONLY.**
**USE A THROWAWAY TEST ACCOUNT AND SMALL PUBLIC TARGETS ONLY.**
**DO NOT RUN THIS ON PERSONAL OR CLIENT ACCOUNTS.**

## Development Journey & Challenges
This project began with a high-level plan centered on modular architecture and operational reliability. I organized the code into clear components (client, scraper, actions, utilities) so each layer could be tested, observed, and hardened independently. I chose instagrapi over Selenium/Playwright because HTTP/GraphQL is faster, more resource-efficient, and less fragile than browser automation.

During implementation, I hit repeated 429 rate-limit responses on public endpoints, especially on `user_id_from_username`. These surfaced quickly when testing against large or popular accounts. I also encountered `BadPassword` errors that persisted across VPNs and mobile data, which was initially confusing because the credentials were correct. This led to a deeper investigation of Instagrapi issues and the realization that Instagram aggressively flags repeated password logins, device fingerprint changes, and rapid retries. The solution was not "retry more" but to reduce login pressure: reusing sessions, preserving device UUIDs, and falling back to password login only when absolutely necessary.

I iteratively hardened the system with tenacity retries, jittered delays, cooldown bursts, and JSONL checkpointing. I introduced session backup files, long post-login cooldowns, and explicit rate-limit detection in the exception chain. This made the bot more resilient and reduced the risk of triggering Instagram's automated defenses.

## Key Learnings & Observations
- Instagram is extremely aggressive against automation, especially on large or popular accounts.
- Public endpoints rate-limit quickly; user lookups can trigger 429 responses even before scraping starts.
- Session persistence and stable device UUIDs are critical to avoid repeated password logins.
- Fresh test accounts and clean IPs (ideally mobile data) produce the most reliable results.
- Retrying blindly increases risk; controlled backoff, cooldowns, and action caps are safer.

## Features
- Modular architecture: dedicated client, scraper, actions, and utility layers.
- Session persistence with backup files and UUID preservation.
- Batch follower scraping with pagination and JSONL checkpointing.
- Action runner with follow + DM sequencing and randomized delays.
- Rate-limit detection with exception-chain 429 checks.
- Tenacity-based retries with exponential backoff and jitter.
- Resume capability after crashes or interrupts.
- Configurable action caps, delays, and dry-run mode.

## Tech Stack
- Python 3.11+
- instagrapi (HTTP/GraphQL client)
- tenacity (retries + backoff)
- python-dotenv (config management)
- requests/urllib3 (network stack)

## Project Structure
```
Instagram_Automation_Bot/
├── main.py
├── bot/
│   ├── instagram_client.py
│   ├── scraper.py
│   ├── actions.py
│   └── utils.py
├── config/
│   └── .env.example
├── data/            # stored followers + checkpoints (gitignored)
├── logs/            # run logs (gitignored)
├── requirements.txt
└── README.md
```

## Setup Instructions
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root:
   ```bash
   cp config/.env.example .env
   ```
4. Update `.env` with a fresh test account:
   ```text
   IG_USERNAME=your_test_username
   IG_PASSWORD=your_test_password
   ```
5. Optional: Remove old sessions before first login:
   ```bash
   rm data/session_*.json
   ```

## Usage Examples
Dry run (scrape only):
```bash
python main.py smallpublicaccount --dry-run
```

Real run with action cap:
```bash
python main.py smallpublicaccount --max-actions 25 --message "Check out our services"
```

Use an existing follower list:
```bash
python main.py smallpublicaccount --followers-path data/followers_smallpublicaccount.jsonl
```

**Note:** Use only small public accounts with < 5k followers for testing.

## CLI Arguments
| Argument | Description | Example |
| --- | --- | --- |
| `target_username` | Public Instagram username to scrape | `smallpublicaccount` |
| `--message` | DM text to send | `"Check out our services"` |
| `--max-actions` | Cap follow+DM actions per run | `--max-actions 25` |
| `--batch-size` | Followers fetched per batch | `--batch-size 200` |
| `--dry-run` | Scrape only, no follow/DM | `--dry-run` |
| `--no-resume` | Ignore saved progress | `--no-resume` |
| `--followers-path` | Use existing JSONL file | `--followers-path data/f.jsonl` |

## How It Works
1. **Login with session**: The client loads a saved session (or backup), validates it via `get_timeline_feed`, and only falls back to password login when necessary. Device UUIDs are preserved to avoid fingerprint changes.
2. **Batch scraping**: Followers are fetched in batches. Each batch is saved incrementally to JSONL, and a progress file stores pagination state for crash recovery.
3. **Action runner**: For each follower, the bot follows first, waits with jitter, then sends a DM. All actions respect configured limits.
4. **Reliability layer**: Tenacity-based retries, exception-chain 429 detection, and cooldown bursts reduce rate-limit risk.

## Rate Limit & Anti-Bot Strategy
- Random jitter between actions: 8-25 seconds.
- Cooldown bursts after every N actions (default 30), for 60-120 seconds.
- Post-login cooldown: 120-180 seconds.
- Exponential backoff with jitter for retryable exceptions.
- 429 detection using exception-chain scanning to stop early and avoid escalation.
- Action caps per run to avoid suspicious spikes.
- Session persistence and fresh test accounts are critical to avoid repeated password logins and IP blacklists.

## Error Handling & Reliability
- **429 rate limits**: Detected and logged explicitly; retries use exponential backoff and may stop early to avoid bans.
- **BadPassword**: Clear guidance in logs recommending a fresh test account and clean IP.
- **Session invalidation**: Automatic re-login while preserving device UUIDs.
- **Network errors**: Retried with tenacity; failures are logged with context.
- **Checkpointing**: Followers and completed actions are written to JSONL for resume after crashes.

## Limitations
- Instagram aggressively blocks automation; success depends on account age and IP reputation.
- Private accounts and challenge flows may require manual intervention.
- Large targets can trigger stricter limits and longer cooldowns.

## Future Improvements
- Optional Selenium/Playwright fallback when API limits are too strict.
- Proxy rotation with health checks and reputation scoring.
- Safer DM templates with personalization to reduce spam signals.
- SQLite-backed storage for better auditability and analytics.
- Support for interactive input (asking username and message at runtime).
