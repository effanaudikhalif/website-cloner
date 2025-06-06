# backend/recreate_site.py

import json
import re
import sys
from pathlib import Path
import asyncio
import anthropic

from scraper import scrape_website
from filter_css import filter_css_from_html_and_css

CONTEXT_FILE = Path(__file__).with_name("context.json")
API_KEY = "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"


def build_minimal_html(summary: dict, title: str) -> str:
    """
    Construct a very small HTML snippet from the scraped summary.
    Only include title, a few headings, buttons, and paragraphs.
    """
    parts = []

    # <header> with title
    parts.append(f"<header><h1>{title}</h1></header>")

    # A few <h2> if present
    for h in summary.get("headings", [])[:3]:
        parts.append(f"<section><h2>{h}</h2></section>")

    # A few <button> tags
    for b in summary.get("buttons", [])[:2]:
        parts.append(f"<button>{b}</button>")

    # A few paragraphs (if any)
    for p in summary.get("paragraphs", [])[:2]:
        parts.append(f"<section><p>{p}</p></section>")

    # You can add nav_links or section_headers similarly if needed.

    return "\n".join(parts)


def format_prompt(min_html: str, filtered_css: str) -> str:
    """
    Build a Claude prompt that includes only:
      1) The minimal HTML snippet (wrapped in ```html```).
      2) The filtered CSS (wrapped in ```css```).
      3) Clear instructions to output HTML+CSS in separate code blocks.
    """
    return (
        "You are given a tiny but representative snippet of HTML plus a matching minimal CSS.\n"
        "Your job: Generate a clean, mobile-friendly, full HTML/CSS page that visually resembles the original site.\n\n"

        "❗️ Do NOT include any JavaScript or third-party CSS frameworks.\n"
        "❗️ Do NOT output any extra text outside the requested code blocks.\n\n"

        "🎯 Requirements:\n"
        "- Use semantic HTML tags like <header>, <main>, <section>, <footer>.\n"
        "- Make it responsive (mobile-first).\n"
        "- Use the CSS provided to guide your colors, spacing, typography, etc., but you may simplify.\n"
        "- Choose a modern sans-serif font.\n"
        "- Keep HTML/CSS minimal and clean.\n\n"

        "Below is the important HTML snippet:\n"
        f"```html\n{min_html}\n```\n\n"

        "Below is the minimal CSS that matches those elements:\n"
        f"```css\n{filtered_css}\n```\n\n"

        "❗️ Return exactly two blocks:\n"
        "- One ```html``` block with your complete page markup.\n"
        "- One ```css``` block with your complete stylesheet.\n"
    )


def extract_code(block_type: str, text: str) -> str:
    """
    Grab content between ```block_type ... ``` in Claude's response.
    """
    pattern = rf"```{block_type}\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        print(f"[DEBUG] Extracted {block_type.upper()} block (length {len(match.group(1))}).")
        return match.group(1).strip()
    else:
        print(f"[DEBUG] Failed to extract {block_type.upper()} block from response.")
        return ""


async def main(url: str) -> None:
    print(f"[DEBUG] Starting full scrape for: {url}")
    context = await scrape_website(url)
    context_dict = context.model_dump()
    print(f"[DEBUG] Dumping full context to context.json...")
    CONTEXT_FILE.write_text(json.dumps(context_dict, indent=2, default=str))

    # 1) Use the *full* HTML (for filtering selectors) but do NOT send to Claude
    full_html = context_dict.get("html", "")
    raw_css = context_dict.get("css_contents", "")

    print(f"[DEBUG] raw_html length: {len(full_html)} chars")
    print(f"[DEBUG] raw_css length: {len(raw_css)} chars")

    # 2) Filter CSS down to only selectors used in the full HTML
    filtered_css = filter_css_from_html_and_css(full_html, raw_css)
    print(f"[DEBUG] filtered_css length: {len(filtered_css)} chars")

    # 3) Build a minimal HTML snippet from your summary + title
    title = context_dict.get("title", "")
    summary = context.summary
    minimal_html = build_minimal_html(summary, title)
    print(f"[DEBUG] minimal_html length: {len(minimal_html)} chars")

    # 4) Build the final prompt for Claude
    prompt = format_prompt(minimal_html, filtered_css)

    print("[DEBUG] Prompt length (chars):", len(prompt))
    # (Optional) print a preview of the prompt if you want to inspect it:
    # print(prompt[:500] + "\n…\n")

    # 5) Send to Claude
    print("[DEBUG] Sending prompt to Claude…")
    client = anthropic.Anthropic(api_key=API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )

    # 6) Gather Claude’s raw response
    text_content = "".join(part.text for part in response.content if hasattr(part, "text"))
    print(f"[DEBUG] Claude response length: {len(text_content)} chars")

    # (Optional) See exactly what Claude returned:
    # print(text_content)

    # 7) Extract HTML and CSS from Claude’s response
    html_result = extract_code("html", text_content)
    css_result = extract_code("css", text_content)

    # 8) Write to files
    Path("recreated_page.html").write_text(html_result)
    Path("styles.css").write_text(css_result)
    print("✅ Written files: recreated_page.html, styles.css")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
