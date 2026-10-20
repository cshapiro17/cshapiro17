"""Render the curated newsletter as email-safe HTML and plain text."""

from __future__ import annotations

from datetime import date
from html import escape


def _byline(paper) -> str:
    authors = ", ".join(paper.authors[:4]) + (" et al." if len(paper.authors) > 4 else "")
    return f"{authors} · {paper.source}" if authors else paper.source


def render_html(title: str, issue: dict, today: date, total_scanned: int) -> str:
    featured = []
    for item in issue["featured"]:
        p = item["paper"]
        featured.append(f"""
        <tr><td style="padding:18px 0;border-bottom:1px solid #e5e7eb;">
          <div style="font-size:12px;color:#2563eb;text-transform:uppercase;letter-spacing:.04em;font-weight:600;">{escape(item["topic"])}</div>
          <a href="{escape(p.url)}" style="display:block;margin:4px 0 2px;font-size:17px;line-height:1.35;font-weight:600;color:#111827;text-decoration:none;">{escape(p.title)}</a>
          <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">{escape(_byline(p))}</div>
          <p style="margin:0 0 8px;font-size:15px;line-height:1.55;color:#1f2937;">{escape(item["summary"])}</p>
          <p style="margin:0;font-size:14px;line-height:1.5;color:#374151;"><strong>Why it matters:</strong> {escape(item["why_it_matters"])}</p>
        </td></tr>""")

    noteworthy = "".join(
        f'<li style="margin:0 0 8px;"><a href="{escape(i["paper"].url)}" style="color:#111827;font-weight:600;">'
        f'{escape(i["paper"].title)}</a> &mdash; <span style="color:#374151;">{escape(i["one_liner"])}</span></li>'
        for i in issue["also_noteworthy"]
    )
    noteworthy_section = (
        f'<h2 style="font-size:16px;margin:28px 0 10px;color:#111827;">Also noteworthy</h2>'
        f'<ul style="padding-left:18px;margin:0;font-size:14px;line-height:1.5;">{noteworthy}</ul>'
        if noteworthy else ""
    )

    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f3f4f6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;border-radius:8px;padding:28px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;">
  <tr><td>
    <div style="font-size:13px;color:#6b7280;">{today.strftime("%A, %B %-d, %Y")}</div>
    <h1 style="font-size:22px;margin:4px 0 14px;color:#111827;">{escape(title)}</h1>
    <p style="margin:0 0 6px;font-size:15px;line-height:1.55;color:#1f2937;">{escape(issue["overview"])}</p>
  </td></tr>
  {"".join(featured)}
  <tr><td>{noteworthy_section}
    <p style="margin:28px 0 0;font-size:12px;color:#9ca3af;">Selected from {total_scanned} new papers on arXiv and journal feeds. Summaries are AI-generated from abstracts; check the paper before relying on a result.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


def render_text(title: str, issue: dict, today: date, total_scanned: int) -> str:
    lines = [title, today.strftime("%A, %B %-d, %Y"), "", issue["overview"], ""]
    for n, item in enumerate(issue["featured"], 1):
        p = item["paper"]
        lines += [
            f"{n}. [{item['topic']}] {p.title}",
            f"   {_byline(p)}",
            f"   {p.url}",
            f"   {item['summary']}",
            f"   Why it matters: {item['why_it_matters']}",
            "",
        ]
    if issue["also_noteworthy"]:
        lines.append("ALSO NOTEWORTHY")
        for i in issue["also_noteworthy"]:
            lines.append(f"- {i['paper'].title} - {i['one_liner']}\n  {i['paper'].url}")
        lines.append("")
    lines.append(f"Selected from {total_scanned} new papers. Summaries are AI-generated from abstracts.")
    return "\n".join(lines)
