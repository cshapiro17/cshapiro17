"""Build and email the daily research newsletter.

Usage:
    python newsletter/main.py            # fetch, summarize, send
    python newsletter/main.py --dry-run  # write newsletter/out/preview.html instead of sending

Environment variables:
    ANTHROPIC_API_KEY   Claude API key
    SMTP_USERNAME       SMTP login, e.g. you@gmail.com
    SMTP_PASSWORD       SMTP password (for Gmail, an App Password)
    NEWSLETTER_TO       Recipient address(es), comma-separated
    SMTP_HOST / SMTP_PORT   Optional, default smtp.gmail.com:465
    NEWSLETTER_FROM     Optional, defaults to SMTP_USERNAME
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import ssl
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from render import render_html, render_text
from sources import fetch_all
from summarize import curate

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state" / "seen.json"
SEEN_RETENTION_DAYS = 30

log = logging.getLogger("newsletter")


def load_seen() -> dict[str, str]:
    try:
        return json.loads(STATE_FILE.read_text())
    except FileNotFoundError:
        return {}


def save_seen(seen: dict[str, str]) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(seen, indent=0, sort_keys=True))


def send_email(subject: str, html: str, text: str) -> None:
    username = os.environ["SMTP_USERNAME"]
    recipients = [r.strip() for r in os.environ["NEWSLETTER_TO"].split(",") if r.strip()]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("NEWSLETTER_FROM") or username
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as smtp:
            smtp.login(username, os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls(context=context)
            smtp.login(username, os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)
    log.info("Sent newsletter to %d recipient(s)", len(recipients))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="write an HTML preview instead of emailing")
    parser.add_argument("--config", type=Path, default=HERE / "config.toml")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = tomllib.loads(args.config.read_text())
    nl = config["newsletter"]

    seen = load_seen()
    papers = [p for p in fetch_all(config) if p.id not in seen]
    log.info("%d new papers after removing ones already sent", len(papers))
    if not papers:
        log.warning("No new papers found; skipping today's newsletter")
        return 0
    papers = papers[: nl["max_candidates"]]

    issue = curate(papers, config)
    today = datetime.now(timezone.utc).date()
    title = nl["title"]
    html = render_html(title, issue, today, len(papers))
    text = render_text(title, issue, today, len(papers))

    if args.dry_run:
        out = HERE / "out"
        out.mkdir(exist_ok=True)
        (out / "preview.html").write_text(html)
        (out / "preview.txt").write_text(text)
        log.info("Wrote preview to %s", out)
        return 0

    send_email(f"{title} — {today.strftime('%b %-d')}", html, text)

    # Only papers Claude saw are marked, so anything past max_candidates gets
    # another chance tomorrow.
    stamp = datetime.now(timezone.utc).isoformat()
    seen.update({p.id: stamp for p in papers})
    save_seen(seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
