# backend/recreate_site.py

import json
import re
import sys
from pathlib import Path
import asyncio
import anthropic

from scraper import scrape_website
from filter_css import filter_css_from_html_and_css

# ── create (or ensure) a “generated” folder next to this script ──
GENERATED_DIR = Path(__file__).parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Where to dump the scraped context
CONTEXT_FILE = GENERATED_DIR / "context.json"

# Your Anthropic API key
API_KEY = "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"


def build_summary_and_minimal_html(context: dict) -> (dict, str):
    summary = {}
    full_title = context.get("title", "")
    site_name = full_title.split("|")[-1].strip() or "Site"

    # 1) NAV LINKS
    nav_links = []
    for href in context.get("summary", {}).get("nav_links", [])[:5]:
        label = href.rstrip("/").split("/")[-1].replace("-", " ").title() or href
        nav_links.append({"href": href, "label": label})
    summary["nav_links"] = nav_links

    # 2) HERO – image, heading, subheading
    hero_img = context.get("images", [None])[0] or ""
    hero_heading = context.get("summary", {}).get("headings", [""])[0]
    paragraphs = context.get("summary", {}).get("paragraphs", [])
    hero_subheading = paragraphs[0] if paragraphs else ""

    # grab the first scraped button text, if any
    scraped_buttons = context.get("summary", {}).get("buttons", [])
    button_text = scraped_buttons[0] if scraped_buttons else None

    # include button only if we actually scraped one
    summary["hero"] = {
        "img": hero_img,
        "heading": hero_heading,
        "subheading": hero_subheading,
        "button_text": button_text  # may be None
    }

    # 3) NEWS CARDS
    cards = []
    for header in context.get("summary", {}).get("section_headers", [])[:3]:
        cards.append({"heading": header, "snippet": "Preview text..."})
    summary["news_cards"] = cards

    # 4) FOOTER LINKS
    footer_links = [{"label": l["label"], "href": l["href"]} for l in nav_links[:4]]
    summary["footer_links"] = footer_links

    # Build the minimal HTML snippet
    parts = []
    # HEADER + NAV
    parts.append(f'<header class="site-header">')
    parts.append(f"  <h1>{full_title}</h1>")
    if nav_links:
        parts.append('  <nav class="main-nav"><ul>')
        for l in nav_links:
            parts.append(f'    <li><a href="{l["href"]}">{l["label"]}</a></li>')
        parts.append("  </ul></nav>")
    parts.append("</header>")

    # HERO
    parts.append('<section class="hero">')
    parts.append(f'  <img src="{hero_img}" alt="{hero_heading}">')
    parts.append('  <div class="hero-text">')
    parts.append(f"    <h2>{hero_heading}</h2>")
    parts.append(f"    <p>{hero_subheading}</p>")
    if button_text:
        parts.append(f"    <button>{button_text}</button>")
    parts.append("  </div>")
    parts.append("</section>")

    # NEWS CARDS
    parts.append('<section class="news-cards"><div class="news-grid">')
    for c in cards:
        parts.append('  <article class="news-card">')
        parts.append(f"    <h3>{c['heading']}</h3>")
        parts.append(f"    <p>{c['snippet']}</p>")
        parts.append('    <a href="#" class="read-more">Read More</a>')
        parts.append("  </article>")
    parts.append("</div></section>")

    # FOOTER
    parts.append('<footer class="site-footer"><div class="footer-links"><ul>')
    for f in footer_links:
        parts.append(f'  <li><a href="{f["href"]}">{f["label"]}</a></li>')
    parts.append("</ul></div></footer>")

    minimal_html = "\n".join(parts)
    return summary, minimal_html


def build_critical_css(filtered_css: str) -> str:
    critical_selectors = [
        r"\bbody\b", r"\bh1\b", r"\bh2\b", r"\bh3\b", r"\ba\b", r"\bbutton\b",
        r"\.site-header\b", r"\.main-nav\b", r"\.hero\b", r"\.hero\s+img\b",
        r"\.hero-text\b", r"\.news-cards\b", r"\.news-grid\b",
        r"\.news-card\b", r"\.read-more\b", r"\.site-footer\b", r"\.footer-links\b"
    ]
    rules = re.findall(r"([^{]+\{[^}]*\})", filtered_css, re.DOTALL)
    critical = [
        rule.strip()
        for rule in rules
        if any(re.search(pat, rule.split("{", 1)[0]) for pat in critical_selectors)
    ]
    return "\n\n".join(critical).strip()


def format_prompt(min_html: str, summary: dict, critical_css: str) -> str:
    summary_json = json.dumps(summary, indent=2)
    return (
        "You are given a JSON summary, a minimal HTML snippet, and a small critical CSS snippet.\n"
        "Recreate a full, responsive, semantic HTML/CSS page that visually resembles the original "
        "website as closely as possible. Do not include any JavaScript or external CSS frameworks.\n\n"
        "❗️ Return exactly two fenced code blocks:\n"
        "   • One ```html``` containing the complete page markup\n"
        "   • One ```css``` containing the complete stylesheet\n\n"
        "Below is the JSON summary:\n"
        f"```json\n{summary_json}\n```\n\n"
        "Below is the minimal HTML snippet:\n"
        f"```html\n{min_html}\n```\n\n"
        "Below is the critical CSS snippet:\n"
        f"```css\n{critical_css}\n```\n\n"
        "✅ Requirements:\n"
        "- Use semantic tags (<header>,<nav>,<section>,<footer>).\n"
        "- Mobile-first responsive layout.\n"
        "- Follow provided colors, spacing, typography.\n"
    )


def extract_code(block_type: str, text: str) -> str:
    fence = rf"```{block_type}\s*(.*?)\s*```"
    match = re.search(fence, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if block_type == "css":
        fallback = re.search(r"```css\s*(.*)$", text, re.DOTALL)
        if fallback:
            return fallback.group(1).strip()
    return ""


async def main(url: str) -> None:
    print(f"[DEBUG] Scraping {url}…")
    ctx = await scrape_website(url)
    ctx_dict = ctx.model_dump()
    CONTEXT_FILE.write_text(json.dumps(ctx_dict, indent=2, default=str))

    filtered = filter_css_from_html_and_css(ctx_dict["html"], ctx_dict["css_contents"])
    critical = build_critical_css(filtered)
    summary, minimal_html = build_summary_and_minimal_html(ctx_dict)
    prompt = format_prompt(minimal_html, summary, critical)

    print("[DEBUG] Sending to Claude…")
    client = anthropic.Anthropic(api_key=API_KEY)
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    raw = "".join(p.text for p in resp.content if hasattr(p, "text"))

    html_out = extract_code("html", raw)
    css_out = extract_code("css", raw)

    (GENERATED_DIR / "recreated_page.html").write_text(html_out)
    (GENERATED_DIR / "styles.css").write_text(css_out)
    print("✅ Done. Files written to generated/")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
