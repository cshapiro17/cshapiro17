# Daily research newsletter

Each morning a GitHub Actions job:

1. Pulls new papers from arXiv (Robotics, Systems & Control, Applied Physics,
   Fluid Dynamics, Classical Physics) and journal feeds (Science Robotics, IEEE RA-L,
   Mechanism and Machine Theory, MSSP, JMPS, IJMS).
2. Drops papers already sent in an earlier issue.
3. Asks Claude to pick the most relevant ones for a mechanical engineering and
   robotics reader, and summarize each: problem, approach, key result, why it matters.
4. Emails the result as an HTML newsletter.

The workflow is `.github/workflows/daily-newsletter.yml`. Topics, sources, and
issue length are set in `config.toml`.

## Setup

1. **Claude API key.** Create one at https://console.anthropic.com.
2. **Gmail App Password** (if sending from Gmail). Turn on 2-Step Verification, then
   create an app password at https://myaccount.google.com/apppasswords.
3. **Repository secrets.** In the repo, go to *Settings → Secrets and variables →
   Actions → New repository secret* and add:

   | Secret | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your Claude API key |
   | `SMTP_USERNAME` | the Gmail address that sends the email |
   | `SMTP_PASSWORD` | the 16-character app password |
   | `NEWSLETTER_TO` | where to deliver it (comma-separate several addresses) |

   To use a provider other than Gmail, add repository *variables* `SMTP_HOST` and
   `SMTP_PORT` (465 for SSL, 587 for STARTTLS).
4. **Test it.** Open *Actions → Daily research newsletter → Run workflow*. The email
   should arrive within a few minutes.

## Delivery time

The schedule is `47 10 * * *`, which is 10:47 UTC (6:47 AM US Eastern). GitHub cron
runs in UTC and can start several minutes late at busy times. GitHub also pauses
scheduled workflows after 60 days with no repository activity. If that happens,
re-enable the workflow from the Actions tab.

## Running locally

```bash
pip install -r newsletter/requirements.txt
export ANTHROPIC_API_KEY=...
python newsletter/main.py --dry-run   # writes newsletter/out/preview.html
```

Without `--dry-run`, it also needs the SMTP variables and sends the email.

## Cost

One Claude call per day over a few hundred abstracts. Typical runs use
100–250K input tokens, which costs roughly $0.40–$1.00 a day on Claude Opus 5.5.
To spend less, lower `max_candidates` or `max_abstract_chars`, or remove
categories in `config.toml`.
