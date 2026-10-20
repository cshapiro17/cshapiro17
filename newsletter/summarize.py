"""Use Claude to pick the most relevant papers and summarize them."""

from __future__ import annotations

import json
import logging

import anthropic

from sources import Paper

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the editor of a daily research newsletter for a mechanical \
engineer who works on robotics. Each morning you receive a list of newly published \
papers and choose the ones most worth their time.

Reader's interests:
{interests}

Pick the {featured} most relevant and significant papers to feature, and up to \
{noteworthy} more worth a one-line mention. Judge from the title and abstract; do not \
invent results, numbers, or claims the abstract does not support. Write for an \
engineer: plain language, concrete about what was built or measured, no hype. If fewer \
papers are genuinely relevant, return fewer."""

SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {
            "type": "string",
            "description": "2-3 sentences on themes across today's papers.",
        },
        "featured": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "Paper number from the list."},
                    "topic": {"type": "string", "description": "Short topic tag, e.g. 'Legged locomotion'."},
                    "summary": {"type": "string", "description": "3-4 sentences: problem, approach, key result."},
                    "why_it_matters": {"type": "string", "description": "One sentence on practical significance."},
                },
                "required": ["index", "topic", "summary", "why_it_matters"],
                "additionalProperties": False,
            },
        },
        "also_noteworthy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "one_liner": {"type": "string"},
                },
                "required": ["index", "one_liner"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overview", "featured", "also_noteworthy"],
    "additionalProperties": False,
}


def _format_papers(papers: list[Paper], max_abstract_chars: int) -> str:
    blocks = []
    for i, p in enumerate(papers):
        authors = ", ".join(p.authors[:6]) + (" et al." if len(p.authors) > 6 else "")
        abstract = p.abstract[:max_abstract_chars] or "(no abstract available)"
        blocks.append(
            f"[{i}] {p.title}\nSource: {p.source}\nAuthors: {authors or 'unknown'}\n"
            f"Abstract: {abstract}"
        )
    return "\n\n".join(blocks)


def curate(papers: list[Paper], config: dict) -> dict:
    """Return {"overview", "featured": [...], "also_noteworthy": [...]} with papers attached."""
    nl = config["newsletter"]
    claude = config["claude"]
    client = anthropic.Anthropic()

    with client.beta.messages.stream(
        model=claude["model"],
        max_tokens=32000,
        system=SYSTEM_PROMPT.format(
            interests=nl["interests"].strip(),
            featured=nl["featured_count"],
            noteworthy=nl["also_noteworthy_count"],
        ),
        messages=[{
            "role": "user",
            "content": "Today's new papers:\n\n" + _format_papers(papers, nl["max_abstract_chars"]),
        }],
        output_config={
            "effort": claude.get("effort", "medium"),
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        # If a safety classifier declines, retry on Anthropic's recommended model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        response = stream.get_final_message()

    log.info("Claude usage: %s input / %s output tokens",
             response.usage.input_tokens, response.usage.output_tokens)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude's response was cut off (max_tokens)")

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)

    def attach(items: list[dict]) -> list[dict]:
        out, used = [], set()
        for item in items:
            i = item["index"]
            if 0 <= i < len(papers) and i not in used:
                used.add(i)
                out.append({**item, "paper": papers[i]})
        return out

    featured = attach(data["featured"])
    featured_ids = {item["index"] for item in featured}
    noteworthy = [i for i in attach(data["also_noteworthy"]) if i["index"] not in featured_ids]
    return {"overview": data["overview"], "featured": featured, "also_noteworthy": noteworthy}
