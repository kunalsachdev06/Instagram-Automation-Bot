# Instagram Automation Bot
Reliable, rate-limit aware Instagram automation for educational demonstrations.

**WARNING / DISCLAIMER (READ FIRST)**

**AUTOMATION VIOLATES INSTAGRAM TERMS OF SERVICE.**
**YOU CAN BE RATE-LIMITED, CHALLENGED, OR PERMANENTLY BANNED.**
**EDUCATIONAL DEMONSTRATION ONLY.**
**USE A THROWAWAY TEST ACCOUNT AND SMALL PUBLIC TARGETS ONLY.**
**DO NOT RUN THIS ON PERSONAL OR CLIENT ACCOUNTS.**

## Development Journey & Challenges
This project began with a high-level plan centered on modular architecture and operational reliability. I organized the code into clear components (client, scraper, actions, utilities) so each layer could be tested, observed, and hardened independently. I moved to Selenium for UI-driven automation to reflect real-world interaction patterns and avoid API authentication issues.

During implementation, I hit repeated rate-limit responses and UI timing issues, especially when testing against large or popular accounts. I also encountered login failures that persisted across VPNs and mobile data, which led to a deeper investigation of Instagram's anti-automation behavior. The solution was not "retry more" but to reduce login pressure, handle popups and verification flows, and rely on reliable UI interactions.

I iteratively hardened the system with retries, jittered delays, cooldown bursts, and JSONL checkpointing. I added diagnostics (screenshots and HTML) for failed logins or modal loading to speed up troubleshooting. This made the bot more resilient and reduced the risk of triggering Instagram's automated defenses.

## Key Learnings & Observations
- Instagram is extremely aggressive against automation, especially on large or popular accounts.
- UI timing and dynamic DOM changes are the main failure modes with Selenium.
- Manual login (one-time) in the automated browser session is the most reliable path for demos.
- Retrying blindly increases risk; controlled waits, cooldowns, and action caps are safer.

## Features
- Modular architecture: dedicated client, scraper, actions, and utility layers.
- Selenium-based login and UI interactions.
- Batch follower scraping with JSONL checkpointing.
- Follow + DM workflow with action limits and random delays.
- Diagnostics: screenshots + HTML on failures.
- Configurable limits, delays, and dry-run mode.

## Tech Stack
- Python 3.11+
- Selenium (UI automation)
- webdriver-manager (ChromeDriver provisioning)
- tenacity (retries + backoff)
- python-dotenv (config management)
- requests/urllib3 (network stack)

## Project Structure
```
Instagram_Automation_Bot/
├── main.py
├── bot/
│   ├── selenium_client.py
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

## Usage Examples
Dry run (scrape only):
```bash
python main.py smallpublicaccount --dry-run
```

Real run with action cap:
```bash
python main.py smallpublicaccount --max-actions 5 --message "Check out our services"
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
| `--max-actions` | Cap follow+DM actions per run | `--max-actions 5` |
| `--batch-size` | Followers fetched per batch | `--batch-size 200` |
| `--dry-run` | Scrape only, no follow/DM | `--dry-run` |
| `--no-resume` | Ignore saved progress | `--no-resume` |
| `--followers-path` | Use existing JSONL file | `--followers-path data/f.jsonl` |

## How It Works
1. **Login via Selenium**: The client opens the login page, fills credentials, and waits for manual confirmation when needed.
2. **Scrape followers**: The followers dialog is opened and scrolled until the list is populated.
3. **Action runner**: Follows and DMs each scraped user with randomized delays.
4. **Reliability layer**: Diagnostics saved when UI flows fail, plus cooldowns and limits to avoid blocks.

## Rate Limit & Anti-Bot Strategy
- Random jitter between actions: 8-25 seconds.
- Cooldown bursts after every N actions (default 30), for 60-120 seconds.
- Action caps per run to avoid suspicious spikes.
- Diagnostics on login/modal failures to reduce blind retries.

## Error Handling & Reliability
- **UI timing issues**: multiple waits and fallbacks for dynamic DOM.
- **Login failures**: screenshot + HTML saved for inspection.
- **Follower modal failures**: diagnostics saved for debugging.
- **Checkpointing**: followers and completed actions written to JSONL for resume.

## Limitations
- Instagram aggressively blocks automation; success depends on account age and IP reputation.
- Private accounts and challenge flows may require manual intervention.
- Large targets can trigger stricter limits and longer cooldowns.

## Future Improvements
- Optional Playwright fallback for improved selector stability.
- Proxy rotation with health checks and reputation scoring.
- Safer DM templates with personalization to reduce spam signals.
- SQLite-backed storage for better auditability and analytics.
- Support for interactive input (asking username and message at runtime).
